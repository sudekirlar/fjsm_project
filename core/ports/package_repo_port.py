# core/ports/package_repo_port.py

from abc import ABC, abstractmethod
from typing import List
from core.models.data_model import PackageDTO

class IPackageRepository(ABC):
    @abstractmethod
    def read_packages(self) -> List[PackageDTO]:
        """Kaynak sistemden tüm paketleri okur."""
        ...
