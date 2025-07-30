# adapters/driving/json_data_reader_adapter.py

import json
from typing import List
from core.models.data_model import JobDTO, TaskDTO


class JsonDataReaderAdapter:
    def __init__(self, json_path: str):
        self.json_path = json_path

    def read_jobs(self) -> List[JobDTO]:
        with open(self.json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        jobs = []
        for job_dict in raw_data["jobs"]:
            job_id = job_dict["job_id"]
            task_list = []
            for task in job_dict["tasks"]:
                task_dto = TaskDTO(
                    name=task["name"],
                    type=task["type"],
                    order=task["order"],
                    count=task.get("count"),  # split için olabilir
                    eligible_machines=task["eligible_machines"]
                )
                task_list.append(task_dto)

            job_dto = JobDTO(job_id=job_id, tasks=task_list)
            jobs.append(job_dto)

        return jobs
