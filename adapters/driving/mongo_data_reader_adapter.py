# adapters/driving/mongo_data_reader_adapter.py

from typing import List
from pymongo import MongoClient

from core.models.data_model import PackageDTO, JobDTO, TaskDTO
from core.ports.package_repo_port import IPackageRepository
from project_config.settings import MONGODB_CONFIG

class MongoReaderAdapter(IPackageRepository):
    def __init__(self):
        self._client = MongoClient(MONGODB_CONFIG["uri"])
        self._col = self._client[MONGODB_CONFIG["db_name"]][MONGODB_CONFIG["collection"]]

    def read_packages(self) -> List[PackageDTO]:
        docs = list(self._col.find({}))
        out: List[PackageDTO] = []
        for d in docs:
            pid = int(d["package_id"])
            deadline = str(d.get("deadline", ""))

            jobs: List[JobDTO] = []
            for j in d.get("jobs", []):
                tasks: List[TaskDTO] = []
                for t in j.get("tasks", []):
                    tasks.append(TaskDTO(
                        name=t["name"],
                        type=t["type"],
                        order=t["order_id"],
                        count=t.get("count"),
                        eligible_machines=t.get("eligible_machines", [])
                    ))
                jobs.append(JobDTO(job_id=int(j["job_id"]), tasks=tasks))

            out.append(PackageDTO(
                package_id=pid,
                deadline=deadline,
                jobs=jobs,
                source="MONGO",
                uid=f"MONGO-{pid}"
            ))
        return out

    def close(self):
        try:
            self._client.close()
        except:
            pass

    def __del__(self):
        self.close()
