

from typing import List, Optional
from datetime import datetime, timezone
import uuid
from pymongo import MongoClient, ASCENDING, DESCENDING
from config.settings import MONGODB_CONFIG
from core.models.data_model import PlanResultDTO

class MongoPlanResultWriter:
    """
    PostgreSQLPlanResultWriter ile aynı arayüz: create_run_record, update_run_status, write_results
    """
    def __init__(self) -> None:
        self._client = MongoClient(MONGODB_CONFIG["uri"])
        self._db = self._client[MONGODB_CONFIG["db_name"]]
        self._meta = self._db["plan_metadata"]
        self._res = self._db["plan_result"]
        # index'ler
        self._meta.create_index([("run_id", ASCENDING)], unique=True)
        self._meta.create_index([("created_at", DESCENDING)])
        self._res.create_index([("run_id", ASCENDING)])
        self._res.create_index([("start_time", ASCENDING)])

    def create_run_record(self, run_id: uuid.UUID) -> None:
        rid = str(run_id)
        now = datetime.now(timezone.utc)
        self._meta.update_one(
            {"run_id": rid},
            {"$setOnInsert": {"run_id": rid, "status": "PENDING", "created_at": now}},
            upsert=True
        )

    def update_run_status(
        self,
        run_id: uuid.UUID,
        status: str,
        *,
        makespan: Optional[int] = None,
        solver_status: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        rid = str(run_id)
        now = datetime.now(timezone.utc)
        upd = {"status": status}
        if status == "RUNNING":
            upd["started_at"] = now
        if status in ("COMPLETED", "FAILED"):
            upd["completed_at"] = now
        if makespan is not None: upd["makespan"] = int(makespan)
        if solver_status is not None: upd["solver_status"] = str(solver_status)
        if error_message is not None: upd["error_message"] = str(error_message)
        self._meta.update_one({"run_id": rid}, {"$set": upd}, upsert=True)

    def write_results(self, run_id: uuid.UUID, results: List[PlanResultDTO]) -> int:
        rid = str(run_id)
        if not results:
            # yine de temizleyelim
            self._res.delete_many({"run_id": rid})
            return 0
        docs = []
        for r in results:
            docs.append({
                "run_id": rid,
                "task_instance_id": int(r.task_instance_id),
                "job_id": int(r.job_id),
                "task_name": r.task_name,
                "assigned_machine": r.assigned_machine,
                "start_time": int(r.start_time),
                "end_time": int(r.end_time),
                "package_uid": r.package_uid,
            })
        self._res.delete_many({"run_id": rid})
        self._res.insert_many(docs)
        return len(docs)
