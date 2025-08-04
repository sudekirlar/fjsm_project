# adapters/driving/json_data_reader_adapter.py

import json
from typing import List
from core.models.data_model import JobDTO, TaskDTO, PackageDTO

class JsonDataReaderAdapter:
    def __init__(self, json_path: str):
        self.json_path = json_path

    def read_packages(self) -> List[PackageDTO]:
        """
        JSON dosyasından işleri okur ve istediğimiz DTO formatında liste şeklinde döner.
        """
        # with open, dosya açmanın güvenli bir yoludur. Dosya bittiğinde otomatik olarak hata alsak bile kapanır.
        with open(self.json_path, "r", encoding="utf-8") as f:
            # Açık olan dosyayı json alır ve Python'ın anlayabileceği bir nesneye yazar.
            # Biz burada raw_data nesnesine atıyoruz.
            raw_data = json.load(f)

        packages = []
        for pkg in raw_data["packages"]:
            package_id = pkg["package_id"]
            deadline = pkg["deadline"]

            job_dtos = []
            for job_dict in pkg["jobs"]:
                job_id = job_dict["job_id"]
                task_dtos = []
                for task in job_dict["tasks"]:
                    task_dto = TaskDTO(
                        name=task["name"],
                        type=task["type"],
                        order=task["order_id"],  # JSON'da artık 'order_id' olarak geliyor
                        count=task.get("count"),
                        eligible_machines=task["eligible_machines"]
                    )
                    task_dtos.append(task_dto)
                job_dtos.append(JobDTO(job_id=job_id, tasks=task_dtos))

            package_dto = PackageDTO(
                package_id=package_id,
                deadline=deadline,
                jobs=job_dtos
            )
            packages.append(package_dto)

        return packages
