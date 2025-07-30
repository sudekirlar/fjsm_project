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
                    instance = self._create_task_instance(
                        task=task,
                        job_id=job.job_id,
                        suffix=None
                    )
                    all_task_instances.append(instance)

                elif task.type == "split":
                    count = task.count or 1
                    valid_machines = self.machine_config.get_available_machines(task.name)
                    if count > len(valid_machines):
                        raise ValueError(
                            f"Split task '{task.name}' for job {job.job_id} "
                            f"wants {count} parts but only {len(valid_machines)} machines are available."
                        )

                    for i in range(count):
                        instance = self._create_task_instance(
                            task=task,
                            job_id=job.job_id,
                            suffix=f"_{i}"
                        )
                        all_task_instances.append(instance)

                else:
                    raise ValueError(f"Unknown task type: {task.type}")

        return all_task_instances

    def _create_task_instance(self, task: TaskDTO, job_id: int, suffix: str | None) -> TaskInstanceDTO:
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
            machine_candidates=self.machine_config.get_available_machines(base_name)
        )
