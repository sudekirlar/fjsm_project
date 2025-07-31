# adapters/driving/json_data_reader_adapter.py

import json
from typing import List
from core.models.data_model import JobDTO, TaskDTO

class JsonDataReaderAdapter:
    def __init__(self, json_path: str):
        self.json_path = json_path

    def read_jobs(self) -> List[JobDTO]:
        """
        JSON dosyasından işleri okur ve istediğimiz DTO formatında liste şeklinde döner.
        """
        # with open, dosya açmanın güvenli bir yoludur. Dosya bittiğinde otomatik olarak hata alsak bile kapanır.
        with open(self.json_path, "r", encoding="utf-8") as f:
            # Açık olan dosyayı json alır ve Python'ın anlayabileceği bir nesneye yazar.
            # Biz burada raw_data nesnesine atıyoruz.
            raw_data = json.load(f)

        # Dönüştüreceğimiz JobDTO nesneleri için boş liste açıyoruz.
        jobs = []
        for job_dict in raw_data["jobs"]: # json dosyası içindeki job'ları döner. Bu döngü her işi ele alır.
            job_id = job_dict["job_id"]   # İşin kimliğini alır. (101, 102...)
            task_list = []                # Görev listesini oluşturmak için boş liste oluşturuyoruz.
            for task in job_dict["tasks"]: # İşin içindeki her bir task'i ele alır.
                task_dto = TaskDTO(
                    name=task["name"],
                    type=task["type"],
                    order=task["order"],
                    count=task.get("count"),  # Burada get ile count yok ise bile çökmek yerine None döner.
                    eligible_machines=task["eligible_machines"]
                )
                task_list.append(task_dto)
                # Oluşturulan listeyi DTO olarak listeye kaydeder.
                # Örneğin JOB101 için kesme ve oyma taskleri varsa bunları alıyoruz.

            # Elimizde oluşmuş task listesini alıp yanına job_id'sini de ekleyerek job_dto nesnesine veriyoruz.
            job_dto = JobDTO(job_id=job_id, tasks=task_list)
            # Bu nesneyi jobs listesine kaydediyoruz.
            jobs.append(job_dto)

        # jobs listesini dönüyoruz.
        return jobs
