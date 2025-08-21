# adapters/driving/postgresql_order_writer_adapter.py

from typing import Optional, List
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from config.settings import POSTGRESQL_CONFIG

class PostgreSQLOrderWriterAdapter:
    def __init__(self):
        self._conn = psycopg2.connect(**POSTGRESQL_CONFIG)

    def close(self):
        try:
            self._conn.close()
        except:
            pass

    def __del__(self):
        self.close()

    def _ensure_package(self, cur, package_id: int, deadline):
        cur.execute("SELECT 1 FROM package WHERE package_id = %s", (package_id,)) # SELECT 1 ile var mı diye bakıyoruz, varsa güncelleyeceğiz, yoksa ekleyeceğiz.
        if cur.fetchone() is None: # Sorgudan satır dönmediyse None dönecek.
            cur.execute( # Package tablosuna bir package bilgisi ekliyoruz.
                "INSERT INTO package (package_id, deadline) VALUES (%s, %s)",
                (package_id, str(deadline))
            )
        else:
            cur.execute( # Kayıt varsa deadline'ı güncelliyoruz belki o değişmiştir diye.
                "UPDATE package SET deadline = %s WHERE package_id = %s",
                (str(deadline), package_id)
            )

    def _ensure_job(self, cur, package_id: int, job_id: int):
        cur.execute("SELECT 1 FROM job WHERE job_id = %s", (job_id,)) # job_id var mı bakıyoruz.
        exists = cur.fetchone() is not None # Sonucu exists'e atıyoruz.
        if not exists: # Job yoksa ekliyoruz.
            cur.execute(
                "INSERT INTO job (job_id, package_id) VALUES (%s, %s)",
                (job_id, package_id)
            )
        else:
            cur.execute( # Job varsa ve mevcut package_id ile yeni package_id farklıysa güncelliyoruz.
                "UPDATE job SET package_id = %s WHERE job_id = %s AND (package_id IS DISTINCT FROM %s)",
                (package_id, job_id, package_id)
            )

    def create_task(
        self,
        package_id: int,
        job_id: int,
        job_type: str,
        mode: str,
        phase: int,
        count: Optional[int],
        eligible_machines: Optional[List[str]],
        deadline,
    ) -> int: # Yeni iş emri girdisini kaydetmek için dışarıdan gelen bilgilerle yeni bir task satırı ekleyeceğiz.
        try:
            with self._conn:
                with self._conn.cursor(cursor_factory=RealDictCursor) as cur: # Cursor’ı as cur olarak isimlendirdik.
                    self._ensure_package(cur, package_id, deadline) # Paket kaydı yoksa ekliyoruz, varsa deadline’ı güncelliyoruz.
                    self._ensure_job(cur, package_id, job_id) # Job kaydı yoksa ekliyoruz, varsa gerekirse package_id düzeltiyoruz.

                    em_json = json.dumps(eligible_machines or []) # Listemizi yazmak için json formatına çevirelim.

                    cur.execute( # Yeni bir task satırı ekleyip ve DB’den dönen task_id’yi istiyoruz. Yani kayıt veriyoruz kimlik istiyoruz.
                        """
                        INSERT INTO task (job_id, name, type, order_id, count, eligible_machines)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING task_id
                        """,
                        (job_id, job_type, mode, phase, count, em_json)
                    )
                    row = cur.fetchone() # RETURNING task_id’nin döndürdüğü tek satırı alalım bakalım task_id var mı?
                    return int(row["task_id"]) if row and "task_id" in row else -1 # row dolu ve içinde task_id anahtarı varsa onu integer’a çevirip döndürelim, yoksa -1 dönsün. (Gerçi direkt exception da atabilirmişim sanırım.)
        except Exception:
            self._conn.rollback()
            raise
