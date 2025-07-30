# core/models/data_model.py

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TaskDTO:
    name: str
    type: str  # "single" veya "split"
    order: int
    count: Optional[int] = None  # sadece split görevlerde kullanılır
    eligible_machines: List[str] = None


@dataclass
class JobDTO:
    job_id: int
    tasks: List[TaskDTO]


@dataclass
class TaskInstanceDTO:
    id: int  # Her bir görev örneği için benzersiz ID
    job_id: int
    order: int
    name: str  # örneğin: "oyma_1"
    machine_candidates: List[str]
    base_name: Optional[str] = None


@dataclass
class PlanResultDTO:
    task_instance_id: int
    job_id: int
    task_name: str  # orijinal ad, örneğin: "oyma_1"
    assigned_machine: str
    start_time: int
    end_time: int
