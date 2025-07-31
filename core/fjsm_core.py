# core/fjsm_core.py

from typing import List
from core.models.data_model import JobDTO, TaskDTO, TaskInstanceDTO
from core.ports.logging_port import ILoggingPort
from project_config.machine_config_loader import MachineConfig
from core.ports.fjsm_port import IFJSMCore

class FJSMCore(IFJSMCore):
    def __init__(self, machine_config: MachineConfig, logger: ILoggingPort):
        self.machine_config = machine_config
        self.logger = logger
        self._task_instance_id_counter = 1

    def process_jobs(self, jobs: List[JobDTO]) -> List[TaskInstanceDTO]:
        """
        Core içinde iş kurallarını kontrol eder, kısıtları düzenler ve tüm iş ve görevleri listeye kaydeder.
        """
        all_task_instances: List[TaskInstanceDTO] = []

        for job in jobs:
            for task in job.tasks:
                if task.type == "single":
                    # List comprehension
                    # Seçilebilecek makineler içindeki  her bir makine "m" için
                    # machine_config'den gelen süreyi kontrol ediyoruz. Eğer makinenin duration'ı 0 veya daha küçükse
                    # bu, o makinenin pasif makine olduğu ve kullanılamadığı anlamına gelir.
                    # Eğer duration büyük ise 0'dan, valid_machines adlı yeni listeye kaydediyoruz.
                    valid_machines = [
                        m for m in task.eligible_machines
                        if self.machine_config.get_duration(task.name, m) > 0
                    ]
                    if not valid_machines:
                        self.logger.error("No valid machines found for task '{}'".format(task.name))
                        raise ValueError(
                            f"Single task '{task.name}' for job {job.job_id} "
                            f"has no valid machines with non-zero duration."
                        )

                    # Her tekil görev için instance yaratıyoruz.
                    instance = self._create_task_instance(
                        task=task,
                        job_id=job.job_id,
                        suffix=None,
                        override_machines=valid_machines
                    )
                    all_task_instances.append(instance)

                elif task.type == "split":
                    # Eğer task_count None ise veya 0 ise onun yerine 1 kullanıyoruz.
                    count = task.count or 1
                    valid_machines = [
                        m for m in task.eligible_machines
                        if self.machine_config.get_duration(task.name, m) > 0
                    ]
                    # Gelen veri tutarlı mı bakıyoruz.
                    # Burada seçilen makinelerin count'tan büyük eşit olması bekleniyor. Bunun kontrolünü yapıyoruz.
                    if count > len(valid_machines):
                        raise ValueError(
                            f"Split task '{task.name}' for job {job.job_id} "
                            f"wants {count} parts but only {len(valid_machines)} machines are available."
                        )

                    # Her gelen task'e paralel işleme mantığı için bir suffix veriyoruz.
                    # Bu döngü count kadar çalışır. (6 ise 6 kez)
                    for i in range(count):
                        instance = self._create_task_instance(
                            task=task,
                            job_id=job.job_id,
                            suffix=f"_{i}",
                            override_machines=valid_machines
                        )
                        all_task_instances.append(instance)

                else:
                    self.logger.error("Unknown task type '{}'".format(task.type))
                    raise ValueError(f"Unknown task type: {task.type}")

        self.logger.debug("Eligible machine count per task count:")
        for t in all_task_instances:
            self.logger.debug(f"{t.name} ({t.job_id}) : {len(t.machine_candidates)} machine: {t.machine_candidates}")

        # Tüm işler ve görevler listesini return ediyoruz.
        return all_task_instances

    def _create_task_instance(
        self,
        task: TaskDTO,
        job_id: int,
        suffix: str | None,
        override_machines: List[str] | None = None
    ) -> TaskInstanceDTO:
        """
        Sadece core içinde yardımcı bir fonksiyondur, tüm bilgilerle yeni bir TaskInstanceDTO yaratır.
        """
        instance_id = self._task_instance_id_counter
        self._task_instance_id_counter += 1

        # Her instance'ın farklı isimde olmasını sağlıyoruz.
        # Eğer suffix none ise instance ismimiz direkt task ismimiz olsun.
        # Eğer suffix var ise task ismimize suffix eklensin diyoruz.
        instance_name = task.name if suffix is None else f"{task.name}{suffix}"
        base_name = task.name

        return TaskInstanceDTO(
            id=instance_id,
            job_id=job_id,
            order=task.order,
            name=instance_name,
            base_name=base_name,
            machine_candidates=override_machines if override_machines is not None else task.eligible_machines
        )
