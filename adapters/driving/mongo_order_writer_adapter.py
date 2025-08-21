# adapters/driving/mongo_order_writer_adapter.py

from typing import Optional, List
from pymongo import MongoClient, ASCENDING
from config.settings import MONGODB_CONFIG

class MongoOrderWriterAdapter:
    def __init__(self):
        self._client = MongoClient(MONGODB_CONFIG["uri"])
        self._db = self._client[MONGODB_CONFIG["db_name"]]
        self._col = self._db[MONGODB_CONFIG["collection"]]
        self._col.create_index([("package_id", ASCENDING)], unique=True) # package_id alanında benzersiz (unique) artan indeks oluşsun diye unique parametresi var.

    def close(self):
        try: self._client.close()
        except: pass

    def create_task( # Dışarıdan gelen verilerle Mongo’da package içinde job’a bir task eklensin; yeni task_id dönsün.
        self,
        package_id: int,
        job_id: int,
        job_type: str,
        mode: str,
        phase: int,
        count: Optional[int],
        eligible_machines: Optional[List[str]],
        deadline,
    ) -> int:
        pkg = self._col.find_one({"package_id": int(package_id)}) # Bu package_id’ye sahip document var mı?
        if not pkg: # Yoksa yeni bir paket dict'i hazırlamak için kolları sıvıyoruz. Daha içinde hiçbir şey yok, alanları koyuyoruz sadece.
            pkg = {"package_id": int(package_id), "deadline": str(deadline), "jobs": []}

        jobs = pkg.get("jobs", []) # Package içindeki iş listesini alalım; yoksa boş liste dönecek.
        job = next((j for j in jobs if int(j.get("job_id")) == int(job_id)), None) # jobs içinde job_id eşleşen ilk job’ı bulalım.
        if not job: # : Job yoksa yeni bir job taslağı oluşturalım, jobs listesine ekleyelim. Maksat Mongo'nun iç içe yapısını işlemek burada.
            job = {"job_id": int(job_id), "tasks": []}
            jobs.append(job)

        new_tid = 1 # Task kimliğini package içinde benzersiz üretmek için 1 verelim.
        for j in jobs: # Paket içindeki tüm job’lardaki tüm task’ları gezelim; en büyük task_id’yi bulup +1 yapalım ki benzersiz ve sıralı task_id'miz olsun.
            for t in j.get("tasks", []):
                try:
                    new_tid = max(new_tid, int(t.get("task_id", 0)) + 1)
                except:  # kötü veri koruması
                    continue

        task_doc = { # Artık eklenecek task'i kurabiliriz.
            "task_id": new_tid,
            "name": job_type,
            "type": mode,
            "order_id": int(phase),
            "count": int(count) if count is not None else None,
            "eligible_machines": list(eligible_machines or []),
        }
        job.setdefault("tasks", []).append(task_doc) # tasks listesi yoksa boş liste koyuyoruz, sonra yeni task’i sona ekliyoruz. setdefault bu key'i alır ve bakar.

        pkg["jobs"] = jobs # Package içinde jobs alanını güncelleyelim.
        self._col.update_one( # package_id eşleşen belgeyi günceller; yoksa oluşturur. Upsert bunu sağlar.
            {"package_id": int(package_id)},
            {"$set": {"deadline": str(deadline), "jobs": jobs}},
            upsert=True
        )
        return int(new_tid) # Yeni task’ın id’sini döndürelim.
