# core/models/data_model.py

from dataclasses import dataclass
# dataclass bize constructor, obj yazdırma, obj karşılaştırmaları gibi işlemleri tek bir decorator ile sağlamamızı sağlar.
from typing import List, Optional

# Core'a bilgi olarak giden kısım.
@dataclass
class TaskDTO:
    name: str
    type: str  # single veya split olabilir.
    order: int # faz
    count: Optional[int] = None  # sadece split görevlerde kullanılır
    eligible_machines: List[str] = None

@dataclass
class JobDTO:
    job_id: int
    tasks: List[TaskDTO]

# Instance'lar split görevler içindir. Eğer bir split görev'den örneğin 5 tane varsa, 5 adet task instance'ı oluşacaktır.
@dataclass
class TaskInstanceDTO:
    id: int  # Oluşan her bir instance'a ayrı id'ler atıyoruz.
    job_id: int
    order: int
    name: str  # iş + suffix hali gibi düşünüyoruz.
    machine_candidates: List[str]  # Bir görevin atanabileceği tam, kuralları kontrol edilmiş liste.
    base_name: Optional[str] = None  # Orijinal görevin ismini tutuyoruz. (suffix eklemek için)

# Solver'ın sonucunu döndürüyoruz. Bunu tutan listemiz.
@dataclass
class PlanResultDTO:
    task_instance_id: int
    job_id: int
    task_name: str  # orijinal ad, örneğin: "oyma_1"
    assigned_machine: str
    start_time: int
    end_time: int
