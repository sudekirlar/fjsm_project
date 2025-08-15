from typing import Optional, List
from pymongo import MongoClient, ASCENDING
from project_config.settings import MONGODB_CONFIG

class MongoOrderWriterAdapter:
    """
    packages koleksiyonunda şu yapıyı varsayar:
    { package_id, deadline, jobs: [ { job_id, tasks: [ {task_id, name, type, order_id, count, eligible_machines[]} ] } ] }
    """
    def __init__(self):
        self._client = MongoClient(MONGODB_CONFIG["uri"])
        self._db = self._client[MONGODB_CONFIG["db_name"]]
        self._col = self._db[MONGODB_CONFIG["collection"]]
        self._col.create_index([("package_id", ASCENDING)], unique=True)

    def close(self):
        try: self._client.close()
        except: pass

    def create_task(
        self,
        package_id: int,
        job_id: int,
        job_type: str,    # kesme|oyma|bükme|yanak_açma
        mode: str,        # single|split
        phase: int,       # order_id
        count: Optional[int],
        eligible_machines: Optional[List[str]],
        deadline,
    ) -> int:
        pkg = self._col.find_one({"package_id": int(package_id)})
        if not pkg:
            pkg = {"package_id": int(package_id), "deadline": str(deadline), "jobs": []}

        jobs = pkg.get("jobs", [])
        job = next((j for j in jobs if int(j.get("job_id")) == int(job_id)), None)
        if not job:
            job = {"job_id": int(job_id), "tasks": []}
            jobs.append(job)

        # basit task_id üretimi (paket içi benzersiz)
        new_tid = 1
        for j in jobs:
            for t in j.get("tasks", []):
                try:
                    new_tid = max(new_tid, int(t.get("task_id", 0)) + 1)
                except:  # kötü veri koruması
                    continue

        task_doc = {
            "task_id": new_tid,
            "name": job_type,
            "type": mode,
            "order_id": int(phase),
            "count": int(count) if count is not None else None,
            "eligible_machines": list(eligible_machines or []),
        }
        job.setdefault("tasks", []).append(task_doc)

        pkg["jobs"] = jobs
        self._col.update_one(
            {"package_id": int(package_id)},
            {"$set": {"deadline": str(deadline), "jobs": jobs}},
            upsert=True
        )
        return int(new_tid)
