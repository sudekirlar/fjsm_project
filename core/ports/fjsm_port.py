# core/ports/fjsm_port.py

from abc import ABC, abstractmethod # Core buraya uymak zorundadır. Bunun decorator'ını import ediyoruz.
from typing import List
from core.models.data_model import JobDTO, TaskInstanceDTO

class IFJSMCore(ABC):
    """
    Görevlerin iş kurallarına göre işlenmesini sağlayan core'un sözleşmesidir.
    """
    @abstractmethod
    def process_jobs(self, jobs: List[JobDTO]) -> List[TaskInstanceDTO]:
        """
        Core içinde iş kurallarını kontrol eder, kısıtları düzenler ve tüm iş ve görevleri listeye kaydeder.
        """
        pass
