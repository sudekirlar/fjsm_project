# adapters/driving/mongo_data_reader_adapter.py

from typing import List
from pymongo import MongoClient
from core.models.data_model import PackageDTO, JobDTO, TaskDTO
from core.ports.package_repo_port import IPackageRepository
from config.settings import MONGODB_CONFIG

class MongoReaderAdapter(IPackageRepository):
    def __init__(self):
        self._client = MongoClient(MONGODB_CONFIG["uri"]) # Config'den bağlantı nesnemiz olan URI'mizi alıyoruz.
        self._col = self._client[MONGODB_CONFIG["db_name"]][MONGODB_CONFIG["collection"]] # Üzerinde sorgulama yapabileceğimiz col nesnemizi yaratıyoruz. Bağlantımızdan veritabanımızın ismini ve collection'ımızı veriyoruz.

    def read_packages(self) -> List[PackageDTO]:
        docs = list(self._col.find({})) # Collection'daki tüm document'leri getiren bir sorgu çalıştırıp listemize koyuyoruz.
        out: List[PackageDTO] = [] # DTO listesini dolduracağımız boş bir liste oluşturup bu listenin PackageDTO nesneleri içereceğini söylüyoruz.
        for d in docs:
            pid = int(d["package_id"]) # Package id zaten integer. Çünkü iş emri girmede front tarafta kullanıcıyı int girmeye zorluyoruz ve başka bir type kabul etmiyoruz ama kontrol amaçlı kalabilir.
            deadline = str(d.get("deadline", "")) # Document'teki deadline alanını get() ile çekiyoruz. Eğer deadline yoksa "" ifadesi almasını sağlayarak çökmelerden korunuyoruz.

            jobs: List[JobDTO] = [] # Her paketin içindeki işleri doldurmak için boş bir liste yaratıyoruz ve diyoruz ki, bu liste JobDTO nesneleri içerecek.
            for j in d.get("jobs", []):
                tasks: List[TaskDTO] = [] # Tasks için boş liste yaratıyoruz ve diyoruz ki, bu liste TaskDTO nesneleri içerecek.
                for t in j.get("tasks", []): # Ham veriyi standart TaskDTO formatına çeviren bir data mapping yapıyoruz.
                    tasks.append(TaskDTO( # Tasks listemizi dolduralım.
                        name=t["name"],
                        type=t["type"],
                        order=t["order_id"],
                        count=t.get("count"), # get() ile güvenli alış. Eğer yoksa None değer alacak.
                        eligible_machines=t.get("eligible_machines", []) # Aynı şekilde eğer yoksa boş liste dönsün ki çökme yaşanmasın.
                    ))
                jobs.append(JobDTO(job_id=int(j["job_id"]), tasks=tasks)) # Oluşturduğumuz tasks listesiyle JobDTO listesini oluşturuyoruz ve bunu yaparken job_id'yi de ekliyoruz. Kafamdaki data model'den aslında yukarı doğru hiyerarşik bir gidişat.

            out.append(PackageDTO( # Son olarak package DTO nesnemizi yaratıyoruz ve kalan gerekli bilgilerle birleştiriyoruz. UID kullanmamızın nedeni verinin hangi veritabanından geldiğini söylemekti. Zamanında var olan database assembler için kullanmıştık, şuan elzem olmasa da bilgi olarak tutabiliriz.
                package_id=pid,
                deadline=deadline,
                jobs=jobs,
                source="MONGO",
                uid=f"MONGO-{pid}"
            ))
        return out # Doldurduğumuz PackageDTO'muzu döndürüyoruz.

    def close(self):
        try:
            self._client.close()
        except:
            pass

    def __del__(self):
        self.close() # Bu class'ın destructor'ı. Bu class'ın nesnesi hafızadan silinirken otomatik çağrılır. Amaç, nesne yok olurken açık bir veritabanı bağlantısı kalmadığından emin olmaktır.
