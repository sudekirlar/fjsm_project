# adapters/config/machine_config_loader.py

import json
from typing import Dict


class MachineConfig:
    def __init__(self, path: str):
        with open(path, 'r', encoding='utf-8') as f:
            self._config: Dict[str, Dict[str, int]] = json.load(f)

    def get_duration(self, task_name: str, machine_name: str) -> int:
        """Görev + makine için süreyi verir. Tanımsızsa 0 döner."""
        return self._config.get(task_name, {}).get(machine_name, 0)

    def get_available_machines(self, task_name: str) -> list[str]:
        """Süresi 0'dan büyük olan makineleri döner."""
        return [m for m, dur in self._config.get(task_name, {}).items() if dur > 0]

    def has_task(self, task_name: str) -> bool:
        return task_name in self._config

    def all_tasks(self) -> list[str]:
        return list(self._config.keys())

    def all_machines(self) -> list[str]:
        all_m = set()
        for machine_map in self._config.values():
            all_m.update(machine_map.keys())
        return sorted(all_m)
