# adapters/config/machine_config_loader.py

import json
from typing import Dict

class MachineConfig:
    def __init__(self, path: str):
        with open(path, 'r', encoding='utf-8') as f:
            # Her bir değeri dict olan bir sözlüğümüz var. Ulaşmak istediğimiz yapı yapılacak iş tipi, makine ve süresi.
            # Dict[str, str, int] diye bir yapı yok.
            # Tuple kullanmak da O(n) karmaşıklığa sahip olduğundan bu şekilde iç içe kullanıyoruz.
            self._config: Dict[str, Dict[str, int]] = json.load(f)

    # _config dict'ine doğrudan erişmek yerine metotlarla erişiyoruz.
    def get_duration(self, task_name: str, machine_name: str) -> int:
        """Görev + makine için süreyi verir. Tanımsızsa 0 döner."""
        # Önce config sözlüğümüzde task_name var mı bakıyoruz.
        # Yoksa boş liste döndürüyoruz ki çökme yaşanmasın.
        # İkinci get ile buna ait machine_name arıyoruz.
        # Yoksa 0 döndürüyoruz ki çökme yaşanmasın.
        return self._config.get(task_name, {}).get(machine_name, 0)

    def get_available_machines(self, task_name: str) -> list[str]:
        """Süresi 0'dan büyük olan makineleri döner."""
        # task_name kesme veya oyma idi.
        # Bu kesme veya oymada, hangisi ise task, onun makineleri items ile taranır.
        # Bu tarama sonucu içinde 0 kontrolü yapılır.
        return [m for m, dur in self._config.get(task_name, {}).items() if dur > 0]

    def has_task(self, task_name: str) -> bool:
        """
        Bu task tanımlı/mevcut mu bakmak için kullanılır.
        """
        # _config dict'i içinde bu task_name tanımlı mı bakmanın verimli yolu in iledir.
        return task_name in self._config

    def all_tasks(self) -> list[str]:
        """
        Tanımlı görevlerin listesini döner.
        """
        # _config listi içinde tarama yapılır.
        # keys, dict için kullanılır.
        # Şuan kesme, oyma döner.
        return list(self._config.keys())

    def all_machines(self) -> list[str]:
        """
        Makinelerin listesini döner.
        """
        # Boş bir küme yaratılır.
        all_m = set()
        # Tüm makinelerin iç makine-süreleri gezilir. (K#1, K#2...)
        for machine_map in self._config.values():
            # Her makinenin ismi kümeye eklenir.
            # Update sayesinde önceden var olanlar eklenmez.
            all_m.update(machine_map.keys())
        # Tüm makineleri alfabetik sıralayarak döndürür.
        return sorted(all_m)
