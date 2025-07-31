# core/fjsm_core.py

from typing import List
from core.models.data_model import JobDTO, TaskDTO, TaskInstanceDTO
from project_config.machine_config_loader import MachineConfig

class FJSMCore:
    def __init__(self, machine_config: MachineConfig):
        self.machine_config = machine_config
        self._task_instance_id_counter = 1

    def process_jobs(self, jobs: List[JobDTO]) -> List[TaskInstanceDTO]:
        all_task_instances: List[TaskInstanceDTO] = []

        for job in jobs:
            for task in job.tasks:
                if task.type == "single":
                    # Single görevlerde de duration > 0 olan makineleri filtrele
                    valid_machines = [
                        m for m in task.eligible_machines
                        if self.machine_config.get_duration(task.name, m) > 0
                    ]
                    if not valid_machines:
                        raise ValueError(
                            f"Single task '{task.name}' for job {job.job_id} "
                            f"has no valid machines with non-zero duration."
                        )

                    instance = self._create_task_instance(
                        task=task,
                        job_id=job.job_id,
                        suffix=None,
                        override_machines=valid_machines
                    )
                    all_task_instances.append(instance)

                elif task.type == "split":
                    count = task.count or 1
                    valid_machines = [
                        m for m in task.eligible_machines
                        if self.machine_config.get_duration(task.name, m) > 0
                    ]
                    if count > len(valid_machines):
                        raise ValueError(
                            f"Split task '{task.name}' for job {job.job_id} "
                            f"wants {count} parts but only {len(valid_machines)} machines are available."
                        )

                    for i in range(count):
                        instance = self._create_task_instance(
                            task=task,
                            job_id=job.job_id,
                            suffix=f"_{i}",
                            override_machines=valid_machines
                        )
                        all_task_instances.append(instance)

                else:
                    raise ValueError(f"Unknown task type: {task.type}")

        print("\n✅ Görev başına atanabilir makine sayısı (filtrelenmiş):")
        for t in all_task_instances:
            print(f"   {t.name} ({t.job_id}) → {len(t.machine_candidates)} makine: {t.machine_candidates}")

        return all_task_instances

    def _create_task_instance(
        self,
        task: TaskDTO,
        job_id: int,
        suffix: str | None,
        override_machines: List[str] | None = None
    ) -> TaskInstanceDTO:
        instance_id = self._task_instance_id_counter
        self._task_instance_id_counter += 1

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
