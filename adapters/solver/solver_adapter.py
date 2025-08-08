# adapters/solver/solver_adapter.py
import os

from ortools.sat.python import cp_model
from core.models.data_model import TaskInstanceDTO, PlanResultDTO
from core.ports.logging_port import ILoggingPort
from project_config.machine_config_loader import MachineConfig
from collections import defaultdict, Counter

class ORToolsSolver:
    def __init__(self, machine_config: MachineConfig, logger: ILoggingPort):
        self.config = machine_config
        self.logger = logger

    def solve(self, tasks: list[TaskInstanceDTO]) -> list[PlanResultDTO]:
        model = cp_model.CpModel()

        # Horizon hesaplama
        max_duration_sum = 0
        for task in tasks:
            durations = [
                self.config.get_duration(task.base_name, m)
                for m in task.machine_candidates
                if self.config.get_duration(task.base_name, m) is not None
            ]
            if durations:
                max_duration_sum += max(durations)

        horizon = int(max_duration_sum * 1.5)

        # Değişken tanımlamaları
        start_vars = {}
        end_vars = {}
        interval_vars = {}
        machine_assignments = {}
        machine_to_tasks = {}

        self.logger.info("Task-Machine correspondence and its duration: ")
        for task in tasks:
            self.logger.info(f"Task: {task.name} ({task.id})")
            for machine in task.machine_candidates:
                duration = self.config.get_duration(task.base_name, machine)
                if duration is None:
                    self.logger.error(f"{machine}'s duration is not found.")
                    continue

                self.logger.debug(f"{machine} : {duration}")
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

            model.add_exactly_one([machine_assignments[task.id, m] for m in task.machine_candidates])

        for machine, intervals in machine_to_tasks.items():
            model.add_no_overlap(intervals)

        # Job–Order gruplama
        job_order_map = defaultdict(lambda: defaultdict(list))
        for task in tasks:
            job_order_map[task.job_id][task.order].append(task)

        # Faz geçişleri (order precedence)
        for job_id, order_map in job_order_map.items():
            orders = sorted(order_map.keys())
            for i in range(len(orders) - 1):
                current_tasks = order_map[orders[i]]
                next_tasks = order_map[orders[i + 1]]

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

                phase_start = model.new_int_var(0, horizon, f"phase{job_id}_{orders[i + 1]}_start")
                model.add_min_equality(phase_start, next_starts)

                model.add(phase_end <= phase_start)

        # Job'ların bitiş zamanlarını hesapla
        job_final_ends = []
        for job_id, order_map in job_order_map.items():
            if not order_map:
                continue
            last_order = max(order_map.keys())
            last_tasks = order_map[last_order]
            job_end_var = model.new_int_var(0, horizon, f"job_end_{job_id}")
            ends = [end_vars[t.id, m] for t in last_tasks for m in t.machine_candidates]
            model.add_max_equality(job_end_var, ends)
            job_final_ends.append(job_end_var)

        # Makespan hesapla
        makespan = model.new_int_var(0, horizon, "makespan")
        model.add_max_equality(makespan, job_final_ends)

        # İkincil hedef: tüm job'ların toplam bitiş süresi
        total_job_completion = model.new_int_var(0, horizon * len(job_final_ends), "total_job_completion")
        model.add(total_job_completion == sum(job_final_ends))

        # Hedefler: lexicographic minimize
        model.minimize(makespan)
        model.minimize(total_job_completion)

        # Solver konfigürasyonu
        self.logger.info("Solver starting...")
        solver = cp_model.CpSolver()
        self.logger.info("Solver detailed log starting...")
        solver.parameters.max_time_in_seconds = 60.0
        solver.parameters.log_search_progress = True
        solver.parameters.log_to_stdout = True
        # solver.parameters.num_search_workers = os.cpu_count() or 4

        status = solver.solve(model)

        results = []
        self.logger.info(f"Solver Status: {solver.StatusName(status)}")
        self.logger.debug(f"Wall time: {solver.WallTime():.3f} s")

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            assignment_counter = Counter()
            assigned_task_ids = set()

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
                            end_time=end,
                            package_uid=task.package_uid,
                        ))
                        self.logger.debug(f"{task.name} ({task.job_id}) : {machine} | {start} : {end}")
                        assignment_counter[machine] += 1
                        assigned_task_ids.add(task.id)
                        break

            unassigned_ids = {t.id for t in tasks} - assigned_task_ids
            if unassigned_ids:
                self.logger.error(f"{len(unassigned_ids)} task did not assigned: {sorted(unassigned_ids)}")

            self.logger.debug("Machine assignments: ")
            for machine, count in assignment_counter.items():
                self.logger.debug(f"{machine}: {count} task")

            self.logger.debug(f"All tasks count: {len(tasks)} / Assigned: {len(results)}")

        else:
            self.logger.warning("No feasible solution found.")
            raise RuntimeError("No feasible solution found.")

        return results

