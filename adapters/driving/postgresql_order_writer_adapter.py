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
        cur.execute("SELECT 1 FROM package WHERE package_id = %s", (package_id,))
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO package (package_id, deadline) VALUES (%s, %s)",
                (package_id, str(deadline))  # tip uyumu için str'e çeviriyoruz
            )
        else:
            cur.execute(
                "UPDATE package SET deadline = %s WHERE package_id = %s",
                (str(deadline), package_id)
            )

    def _ensure_job(self, cur, package_id: int, job_id: int):
        cur.execute("SELECT 1 FROM job WHERE job_id = %s", (job_id,))
        exists = cur.fetchone() is not None
        if not exists:
            cur.execute(
                "INSERT INTO job (job_id, package_id) VALUES (%s, %s)",
                (job_id, package_id)
            )
        else:
            cur.execute(
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
    ) -> int:
        try:
            with self._conn:
                with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                    self._ensure_package(cur, package_id, deadline)
                    self._ensure_job(cur, package_id, job_id)

                    em_json = json.dumps(eligible_machines or [])

                    cur.execute(
                        """
                        INSERT INTO task (job_id, name, type, order_id, count, eligible_machines)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING task_id
                        """,
                        (job_id, job_type, mode, phase, count, em_json)
                    )
                    row = cur.fetchone()
                    return int(row["task_id"]) if row and "task_id" in row else -1
        except Exception:
            self._conn.rollback()
            raise
