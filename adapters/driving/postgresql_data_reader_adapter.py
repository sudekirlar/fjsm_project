# adapters/driving/postgresql_data_reader_adapter.py

from typing import List
import psycopg2
from psycopg2.extras import RealDictCursor # Sonuçları Dict olarak almamızı sağlar. ("değer1", "değer2") yerine {"değer1": "değer_1"} gibi döner.
from core.models.data_model import PackageDTO, JobDTO, TaskDTO
from core.ports.package_repo_port import IPackageRepository
from config.settings import POSTGRESQL_CONFIG

class PostgreSQLReaderAdapter(IPackageRepository):
    def __init__(self):
        # Bağlantı bilgilerini config'den çekip bağlantı nesnemizi oluşturalım.
        self._conn = psycopg2.connect(
            dbname=POSTGRESQL_CONFIG["dbname"],
            user=POSTGRESQL_CONFIG["user"],
            password=POSTGRESQL_CONFIG["password"],
            host=POSTGRESQL_CONFIG["host"],
            port=POSTGRESQL_CONFIG["port"]
        )

    def read_packages(self) -> List[PackageDTO]:
        try:
            # with bloğu cursor'ın işi bittiğinde veya hata olduğunda otomatik olarak kapanmayı sağlar. Rollback sağlanmış olur.
            # Parantez içi ifadeyle diyoruz ki bana bu türden dön.
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM package") # Tüm paketleri getir.
                package_rows = cur.fetchall() # Dönen tüm satırları bir listeye alalım.

                packages: List[PackageDTO] = [] # packages adında bir liste oluşturup bu liste PackageDTO nesneleri alacak diyoruz.
                for pkg in package_rows:
                    package_id = pkg["package_id"]
                    deadline = pkg["deadline"]
                    # Mevcut pakete ait tüm işlemleri getirelim.
                    # Burada %s kullanımı ile SQL Injection'lara karşı engel yapıyormuşuz.
                    cur.execute("SELECT * FROM job WHERE package_id = %s", (package_id,))
                    job_rows = cur.fetchall()
                    # Asıl amaç task katmanına inmek. Aynı mantığı job'a da yapalım.
                    jobs: List[JobDTO] = []

                    for job in job_rows:
                        job_id = job["job_id"]

                        cur.execute("SELECT * FROM task WHERE job_id = %s", (job_id,))
                        task_rows = cur.fetchall()
                        tasks: List[TaskDTO] = []

                        for task in task_rows:
                            raw = task["eligible_machines"]
                            machines = raw.strip("[]").replace("'", "").replace('"', '').split(", ") if raw else []
                            # Task katmanına indik şimdi tekrar yukarıya doğru katmansal çıkalım.
                            tasks.append(TaskDTO(
                                name=task["name"],
                                type=task["type"],
                                order=task["order_id"],
                                count=task["count"],
                                eligible_machines=machines
                            ))
                        # Olan tasklere şimdi bir de çektiğimiz job'ları ekleyelim.
                        jobs.append(JobDTO(job_id=job_id, tasks=tasks))

                    # En üst katmana ve core'un kabul edeceği paket hazır.
                    packages.append(PackageDTO(
                        package_id=package_id,
                        deadline=str(deadline),
                        jobs=jobs,
                        source="PG",
                        uid=f"PG-{package_id}"
                    ))
                return packages
        except Exception:
            # Eğer olur da try bloğunda bir hata olursa o ana kadar yapılmış olan commit edilmemiş tüm işlemleri geri alalım.
            # Böylelikle veritabanı bir hata durumunda saçma sapan bir aşamada kalmış olmasın.
            # Context manager aslında, yap her şey tam takır olacak ya da başa saracağız. (Atomiklik)
            self._conn.rollback()
            raise

    def close(self):
        try:
            self._conn.close()
        except:
            pass

    def __del__(self):
        self.close()
