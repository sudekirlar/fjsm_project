# core/fjsm_core.py

from typing import List
from core.models.data_model import JobDTO, TaskDTO, TaskInstanceDTO, PackageDTO
from core.ports.logging_port import ILoggingPort
from project_config.machine_config_loader import MachineConfig
from core.ports.fjsm_port import IFJSMCore

class FJSMCore(IFJSMCore):
    def __init__(self, machine_config: MachineConfig, logger: ILoggingPort):
        self.machine_config = machine_config
        self.logger = logger
        self._task_instance_id_counter = 1

    def process_packages(self, packages: List[PackageDTO]) -> List[TaskInstanceDTO]:
        all_task_instances: List[TaskInstanceDTO] = []

        for package in packages:
            for job in package.jobs:
                for task in job.tasks:
                    task_key = task.name.replace(" ", "_")
                    valid_machines = [
                        m for m in task.eligible_machines
                        if self.machine_config.get_duration(task_key, m) > 0
                    ]

                    if not valid_machines:
                        self.logger.error(f"No valid machines for task '{task.name}' in job {job.job_id}")
                        raise ValueError(
                            f"Task '{task.name}' in job {job.job_id} has no valid machines."
                        )

                    if task.type == "single":
                        instance = self._create_task_instance(
                            task=task,
                            job_id=job.job_id,
                            package_id=package.package_id,
                            suffix=None,
                            override_machines=valid_machines
                        )
                        all_task_instances.append(instance)

                    elif task.type == "split":
                        count = task.count or 1
                        if count > len(valid_machines):
                            raise ValueError(
                                f"Split task '{task.name}' in job {job.job_id} "
                                f"wants {count} parts but only {len(valid_machines)} machines available."
                            )
                        for i in range(count):
                            instance = self._create_task_instance(
                                task=task,
                                job_id=job.job_id,
                                package_id=package.package_id,
                                suffix=f"_{i}",
                                override_machines=valid_machines
                            )
                            all_task_instances.append(instance)

                    else:
                        self.logger.error(f"Unknown task type '{task.type}' in job {job.job_id}")
                        raise ValueError(f"Unknown task type: {task.type}")

        self.logger.debug(f"Toplam task instance sayısı: {len(all_task_instances)}")

        # Eğer çok fazlaysa ilk 1000 instance ile sınırlıyoruz.
        if len(all_task_instances) > 500:
            self.logger.warning("Task instance sayısı 1000'i geçti. İlk 1000 ile sınırlandırılıyor.")
            return all_task_instances[:1000]

        return all_task_instances

    def _create_task_instance(
        self,
        task: TaskDTO,
        job_id: int,
        package_id: int,
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
        base_name = task.name.replace(" ", "_")
        return TaskInstanceDTO(
            id=instance_id,
            job_id=job_id,
            package_id=package_id,
            order=task.order,
            name=instance_name,
            base_name=base_name,
            machine_candidates=override_machines if override_machines is not None else task.eligible_machines
        )
