# services/database_assembler.py

from typing import Dict, List
from core.models.data_model import PackageDTO
from core.ports.package_repo_port import IPackageRepository

class PGMangoAssembler:
    """
    Birden çok repository'den paketleri okur ve TEK LİSTE halinde döner.
    Merge yok; "concat" yaklaşımı.
    """
    def __init__(self, repos: Dict[str, IPackageRepository]):
        self.repos = repos

    def read_all(self) -> List[PackageDTO]:
        all_packages: List[PackageDTO] = []
        for _name, repo in self.repos.items():
            pkgs = repo.read_packages() or []
            all_packages.extend(pkgs)
        # (Opsiyonel) UID çakışması kontrolü
        seen = set()
        for p in all_packages:
            if p.uid in seen:
                raise ValueError(f"Duplicate package uid: {p.uid}")
            seen.add(p.uid)
        return all_packages
