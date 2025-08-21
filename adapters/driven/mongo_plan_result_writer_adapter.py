# adapters/driven/mongo_plan_result_writer_adapter.py

from typing import List, Optional
from datetime import datetime, timezone
import uuid
from pymongo import MongoClient, ASCENDING, DESCENDING
from config.settings import MONGODB_CONFIG
from core.models.data_model import PlanResultDTO

class MongoPlanResultWriter:
    def __init__(self) -> None:
        self._client = MongoClient(MONGODB_CONFIG["uri"]) # Mongo bağlantı açarken pool sağlıyormuş, hap bilgi :)
        self._db = self._client[MONGODB_CONFIG["db_name"]]
        self._meta = self._db["plan_metadata"]
        self._res = self._db["plan_result"]
        # Index'lerimi oluşturalım. Bunlar tablo yapım gereği gerekli.
        self._meta.create_index([("run_id", ASCENDING)], unique=True)
        self._meta.create_index([("created_at", DESCENDING)])
        self._res.create_index([("run_id", ASCENDING)])
        self._res.create_index([("start_time", ASCENDING)])

    def create_run_record(self, run_id: uuid.UUID) -> None:
        rid = str(run_id)
        now = datetime.now(timezone.utc)
        self._meta.update_one( # run_id yoksa ekleyelim, varsa dokunmayalım. Bu upsert sayesinde oluyor.
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
    ) -> None: # Run’ın durumunu ve KPI kartlar için bilgileri güncelleyelim.
        rid = str(run_id)
        now = datetime.now(timezone.utc)
        upd = {"status": status} # Güncellenecek alanları toplayacağımız dict’i başlatalım.
        if status == "RUNNING":
            upd["started_at"] = now # RUNNING’e geçtiği anı kaydeder.
        if status in ("COMPLETED", "FAILED"):
            upd["completed_at"] = now # Çalışma tamamlandığında/kaybedildiğinde bitiş zamanını yazar.
        if makespan is not None: upd["makespan"] = int(makespan) # Çözülen planın makespan'ını varsa int’e çevirip ekleyelim.
        if solver_status is not None: upd["solver_status"] = str(solver_status) # Solver'ın çözüm durumunu ekleyelim.
        if error_message is not None: upd["error_message"] = str(error_message) # Error varsa mesajı da verelim.
        self._meta.update_one({"run_id": rid}, {"$set": upd}, upsert=True) # İlgili run kaydını güncelleyelim; yoksa upsert=True ile oluşturalım.

    def write_results(self, run_id: uuid.UUID, results: List[PlanResultDTO]) -> int:
        rid = str(run_id)
        if not results:
            # Sonuç listesi boşsa, yine de eski sonuçları silelim ve 0 dönelim. (Güvenlik için iyi pratik)
            self._res.delete_many({"run_id": rid})
            return 0
        docs = []
        for r in results:
            docs.append({ # Mongo'ya gönderelim gitsin.
                "run_id": rid,
                "task_instance_id": int(r.task_instance_id),
                "job_id": int(r.job_id),
                "task_name": r.task_name,
                "assigned_machine": r.assigned_machine,
                "start_time": int(r.start_time),
                "end_time": int(r.end_time),
                "package_uid": r.package_uid,
            })
        self._res.delete_many({"run_id": rid}) # Eski sonuç satırlarını toplu silelim varsa.
        self._res.insert_many(docs) # Yeni sonuçları topluca ekleyelim.
        return len(docs)
