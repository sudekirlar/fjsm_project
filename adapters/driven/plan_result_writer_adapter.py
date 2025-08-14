# adapters/driven/plan_result_writer_adapter.py
from typing import List, Optional
import uuid
import psycopg2
from psycopg2.extras import execute_values, register_uuid
from project_config.settings import POSTGRESQL_CONFIG
from core.models.data_model import PlanResultDTO


class PostgreSQLPlanResultWriter:
    def __init__(self) -> None:
        # Not: Her fonksiyon kendi bağlantısını yönetecek ki Celery process'leri arasında sorun olmasın.
        pass

    def _get_connection(self):
        conn = psycopg2.connect(**POSTGRESQL_CONFIG)
        # UUID tipini kaydediyoruz.
        register_uuid(conn_or_curs=conn)
        return conn

    def create_run_record(self, run_id: uuid.UUID) -> None:
        # plan_metadata tablosuna PENDING bilgisini gönderiyoruz.
        sql = "INSERT INTO plan_metadata (run_id, status) VALUES (%s, 'PENDING')"
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (run_id,))
            conn.commit()
        finally:
            conn.close()

    def update_run_status(
            self,
            run_id: uuid.UUID,
            status: str,
            *,
            makespan: Optional[int] = None,
            solver_status: Optional[str] = None,
            error_message: Optional[str] = None
    ) -> None:
        set_clauses = [
            "status = %s",
            "completed_at = CASE WHEN %s IN ('COMPLETED', 'FAILED') THEN NOW() ELSE completed_at END",
            "started_at = CASE WHEN %s = 'RUNNING' THEN NOW() ELSE started_at END",
            "makespan = COALESCE(%s, makespan)",
            "solver_status = COALESCE(%s, solver_status)",
            "error_message = COALESCE(%s, error_message)",
        ]
        sql = f"UPDATE plan_metadata SET {', '.join(set_clauses)} WHERE run_id = %s"

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (status, status, status, makespan, solver_status, error_message, run_id))
            conn.commit()
        finally:
            conn.close()

    def write_results(self, run_id: uuid.UUID, results: List[PlanResultDTO]) -> int:
        if not results:
            return 0

        sql = """
            INSERT INTO plan_result
                (run_id, task_instance_id, job_id, task_name, assigned_machine, start_time, end_time, package_uid)
            VALUES %s
        """
        rows = [
            (
                run_id, r.task_instance_id, r.job_id, r.task_name,
                r.assigned_machine, r.start_time, r.end_time, r.package_uid
            ) for r in results
        ]

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                execute_values(cur, sql, rows)
            conn.commit()
            return len(rows)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()