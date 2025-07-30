from ortools.sat.python import cp_model
from core.models.data_model import TaskInstanceDTO, PlanResultDTO
from project_config.machine_config_loader import MachineConfig
from collections import defaultdict


class ORToolsSolver:
    def __init__(self, machine_config: MachineConfig):
        self.config = machine_config

    def solve(self, tasks: list[TaskInstanceDTO]) -> list[PlanResultDTO]:
        model = cp_model.CpModel()
        horizon = 10000

        start_vars = {}
        end_vars = {}
        interval_vars = {}
        machine_assignments = {}
        machine_to_tasks = {}

        # === 1. Görev başlatma, bitiş, atama değişkenleri ===
        for task in tasks:
            for machine in task.machine_candidates:
                duration = self.config.get_duration(task.base_name, machine)
                suffix = f"_{task.id}_{machine}"
                start = model.new_int_var(0, horizon, f"start{suffix}")
                end = model.new_int_var(0, horizon, f"end{suffix}")
                is_assigned = model.new_bool_var(f"assign{suffix}")

                interval = model.new_optional_interval_var(
                    start, duration, end, is_assigned, f"interval{suffix}"
                )
                interval_vars[(task.id, machine)] = interval
                start_vars[(task.id, machine)] = start
                end_vars[(task.id, machine)] = end
                machine_assignments[(task.id, machine)] = is_assigned

                machine_to_tasks.setdefault(machine, []).append(interval)

            # Her görev yalnızca 1 makineye atanmalı
            model.add(sum(machine_assignments[task.id, m] for m in task.machine_candidates) == 1)

        # === 2. Aynı makineye gelen işler çakışmasın ===
        for machine, intervals in machine_to_tasks.items():
            model.add_no_overlap(intervals)

        # === 3. Job faz sıralaması (tüm görevler sıralı fazlara uysun) ===
        job_order_map = defaultdict(lambda: defaultdict(list))
        for task in tasks:
            job_order_map[task.job_id][task.order].append(task)

        for job_id, order_map in job_order_map.items():
            orders = sorted(order_map.keys())
            for i in range(len(orders) - 1):
                current_tasks = order_map[orders[i]]
                next_tasks = order_map[orders[i + 1]]

                # Faz geçişinde her t1 → t2 bağımlılığı tanımla (opsiyonel ama granular)
                for t1 in current_tasks:
                    for t2 in next_tasks:
                        for m1 in t1.machine_candidates:
                            for m2 in t2.machine_candidates:
                                model.add(
                                    end_vars[t1.id, m1] <= start_vars[t2.id, m2]
                                ).only_enforce_if(
                                    machine_assignments[t1.id, m1]
                                ).only_enforce_if(
                                    machine_assignments[t2.id, m2]
                                )

                # Faz geçişini grup olarak da sabitle (faz tamamı bitmeden yeni faz başlamasın)
                current_ends = [
                    end_vars[t.id, m]
                    for t in current_tasks
                    for m in t.machine_candidates
                ]
                next_starts = [
                    start_vars[t.id, m]
                    for t in next_tasks
                    for m in t.machine_candidates
                ]

                phase_end = model.new_int_var(0, horizon, f"phase{job_id}_{orders[i]}_end")
                model.add_max_equality(phase_end, current_ends)

                phase_start = model.new_int_var(0, horizon, f"phase{job_id}_{orders[i+1]}_start")
                model.add_min_equality(phase_start, next_starts)

                model.add(phase_end <= phase_start)

        # === 4. Makespan hedefi ===
        all_ends = [end_vars[task.id, m] for task in tasks for m in task.machine_candidates]
        makespan = model.new_int_var(0, horizon, "makespan")
        model.add_max_equality(makespan, all_ends)
        model.minimize(makespan)

        # === 5. Çöz ===
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        results = []

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for task in tasks:
                for machine in task.machine_candidates:
                    if solver.boolean_value(machine_assignments[task.id, machine]):
                        start = solver.value(start_vars[task.id, machine])
                        end = solver.value(end_vars[task.id, machine])
                        results.append(PlanResultDTO(
                            task_instance_id=task.id,
                            job_id=task.job_id,
                            task_name=task.name,
                            assigned_machine=machine,
                            start_time=start,
                            end_time=end
                        ))
                        break
        else:
            raise RuntimeError("No feasible solution found.")

        return results
