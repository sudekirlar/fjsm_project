# adapters/driving/postgresql_data_reader_adapter.py

from typing import List
import psycopg2
from psycopg2.extras import RealDictCursor
from core.models.data_model import PackageDTO, JobDTO, TaskDTO
from project_config.settings import POSTGRESQL_CONFIG

class PostgreSQLDataReaderAdapter:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=POSTGRESQL_CONFIG["dbname"],
            user=POSTGRESQL_CONFIG["user"],
            password=POSTGRESQL_CONFIG["password"],
            host=POSTGRESQL_CONFIG["host"],
            port=POSTGRESQL_CONFIG["port"]
        )

    def read_packages(self) -> List[PackageDTO]:
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM package")
                package_rows = cur.fetchall()

                packages: List[PackageDTO] = []

                for pkg in package_rows:
                    package_id = pkg["package_id"]
                    deadline = pkg["deadline"]

                    cur.execute("SELECT * FROM job WHERE package_id = %s", (package_id,))
                    job_rows = cur.fetchall()
                    jobs: List[JobDTO] = []

                    for job in job_rows:
                        job_id = job["job_id"]

                        cur.execute("SELECT * FROM task WHERE job_id = %s", (job_id,))
                        task_rows = cur.fetchall()
                        tasks: List[TaskDTO] = []

                        for task in task_rows:
                            cur.execute(
                                "SELECT machine_name FROM task_machine WHERE task_id = %s",
                                (task["task_id"],)
                            )
                            machine_codes = [row["machine_name"] for row in cur.fetchall()]

                            task_dto = TaskDTO(
                                name=task["name"],
                                type=task["type"],
                                order=task["order_id"],
                                count=task["count"],
                                eligible_machines=machine_codes
                            )
                            tasks.append(task_dto)

                        jobs.append(JobDTO(job_id=job_id, tasks=tasks))

                    packages.append(PackageDTO(
                        package_id=package_id,
                        deadline=deadline,
                        jobs=jobs
                    ))

                return packages
        except Exception as e:
            self.conn.rollback()
            raise e

    def close(self):
        self.conn.close()

    def __del__(self):
        self.close()

