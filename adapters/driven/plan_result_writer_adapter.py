# adapters/driven/plan_result_writer_adapter.py
from typing import List, Optional
import uuid
import psycopg2
from psycopg2.extras import execute_values, register_uuid
from project_config.settings import POSTGRESQL_CONFIG
from core.models.data_model import PlanResultDTO


class PostgreSQLPlanResultWriter:
    """
    plan_metadata'ya stub (FK için) + plan_result'a toplu insert yapar.
    Tek transaction kullanır, hata olursa rollback.
    """
    def __init__(self) -> None:
        self._conn = psycopg2.connect(
            dbname=POSTGRESQL_CONFIG["dbname"],
            user=POSTGRESQL_CONFIG["user"],
            password=POSTGRESQL_CONFIG["password"],
            host=POSTGRESQL_CONFIG["host"],
            port=POSTGRESQL_CONFIG["port"],
        )
        self._conn.autocommit = False

        # UUID type caster'ı kaydet (psycopg2 sürümlerine uyumlu)
        try:
            register_uuid(conn_or_curs=self._conn)  # doğru isim
        except TypeError:
            # Bazı eski sürümlerde yalnızca positional arg kabul ediyor
            register_uuid(self._conn)

    def insert_run_and_results(
        self,
        run_id: uuid.UUID,
        results: List[PlanResultDTO],
        *,
        status_init: str = "RUNNING",       # plan_metadata.status (başlangıç)
        solver_status_init: str = "N/A",    # plan_metadata.solver_status (başlangıç)
        status_final: str = "COMPLETED",    # plan_metadata.status (bitiş)
        solver_status_final: Optional[str] = None,  # biliniyorsa geç
        error_message: Optional[str] = None
    ) -> int:
        """
        - plan_metadata'ya stub satırı yazar (created_at/started_at = now()).
        - plan_result'a batch insert yapar.
        - plan_metadata'yı tamamlanma bilgileriyle günceller (completed_at, makespan, status, solver_status, error_message).
        Döndürdüğü değer: yazılan plan_result satır sayısı.
        """
        if not results:
            # Yine de metadata stub'ı at; status'u 'EMPTY' bırakmak istersen parametreyle geçebilirsin.
            try:
                with self._conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO plan_metadata (run_id, status, created_at, started_at, solver_status)
                        VALUES (%s, %s, now(), now(), %s)
                        ON CONFLICT (run_id) DO NOTHING
                        """,
                        (run_id, status_init, solver_status_init),
                    )
                    cur.execute(
                        """
                        UPDATE plan_metadata
                        SET completed_at = now(),
                            status = %s,
                            solver_status = COALESCE(%s, solver_status),
                            error_message = %s
                        WHERE run_id = %s
                        """,
                        (status_final, solver_status_final, error_message, run_id),
                    )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                self._safe_close()
            return 0

        # makespan'ı results üzerinden hesaplayalım (max end_time).
        computed_makespan = max(r.end_time for r in results)

        try:
            with self._conn.cursor() as cur:
                # 1) FK için metadata stub
                cur.execute(
                    """
                    INSERT INTO plan_metadata (run_id, status, created_at, started_at, solver_status)
                    VALUES (%s, %s, now(), now(), %s)
                    ON CONFLICT (run_id) DO NOTHING
                    """,
                    (run_id, status_init, solver_status_init),
                )

                # 2) plan_result batch insert
                rows = [
                    (
                        run_id,
                        r.task_instance_id,
                        r.job_id,
                        r.task_name,
                        r.assigned_machine,
                        r.start_time,
                        r.end_time,
                        r.package_uid,
                    )
                    for r in results
                ]

                execute_values(
                    cur,
                    """
                    INSERT INTO plan_result
                        (run_id, task_instance_id, job_id, task_name, assigned_machine, start_time, end_time, package_uid)
                    VALUES %s
                    """,
                    rows,
                )

                # 3) metadata finalize
                cur.execute(
                    """
                    UPDATE plan_metadata
                    SET completed_at = now(),
                        makespan = %s,
                        status = %s,
                        solver_status = COALESCE(%s, solver_status),
                        error_message = %s
                    WHERE run_id = %s
                    """,
                    (
                        computed_makespan,
                        status_final,
                        solver_status_final,
                        error_message,
                        run_id,
                    ),
                )

            self._conn.commit()
            return len(results)

        except Exception:
            self._conn.rollback()
            raise
        finally:
            self._safe_close()

    def _safe_close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
