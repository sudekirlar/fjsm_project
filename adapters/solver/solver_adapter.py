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
                if self.config.get_duration(task.base_name, m) > 0  # CHANGED: None yerine >0
            ]
            if durations:
                max_duration_sum += max(durations)

        horizon = int(max_duration_sum * 1.5)

        # Değişken tanımlamaları
        start_vars = {}           # (task.id, machine) -> IntVar
        end_vars = {}             # (task.id, machine) -> IntVar
        interval_vars = {}        # (task.id, machine) -> OptionalIntervalVar
        machine_assignments = {}  # (task.id, machine) -> BoolVar
        machine_to_tasks = {}     # machine -> list[OptionalIntervalVar]

        # Master interval (faz/öncelik bunlar üzerinden)
        master_start = {}         # task.id -> IntVar
        master_dur = {}           # task.id -> IntVar
        master_end = {}           # task.id -> IntVar
        master_interval = {}      # task.id -> IntervalVar

        self.logger.info("Task-Machine correspondence and its duration: ")
        for task in tasks:
            self.logger.info(f"Task: {task.name} ({task.id})")

            # Geçerli makine-süreleri
            durations_map = {}
            for machine in task.machine_candidates:
                d = self.config.get_duration(task.base_name, machine)
                if d and d > 0:
                    durations_map[machine] = d
                else:
                    self.logger.error(f"{machine}'s duration is not found or zero for task {task.name}.")

            if not durations_map:
                raise ValueError(f"No valid machine durations for task {task.name} ({task.id})")

            # MASTER interval: süre aralıklı
            min_d = min(durations_map.values())
            max_d = max(durations_map.values())
            ms = model.new_int_var(0, horizon, f"tstart_{task.id}")
            md = model.new_int_var(min_d, max_d, f"tdur_{task.id}")
            me = model.new_int_var(0, horizon, f"tend_{task.id}")
            mi = model.new_interval_var(ms, md, me, f"tiv_{task.id}")

            master_start[task.id] = ms
            master_dur[task.id] = md
            master_end[task.id] = me
            master_interval[task.id] = mi

            # Makine alternatifleri: opsiyonel interval + atama bool
            assign_literals = []
            for machine, duration in durations_map.items():
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
                assign_literals.append(is_assigned)

                # NoOverlap için makineye ata
                machine_to_tasks.setdefault(machine, []).append(interval)

                # >>> Alternative eşlemesi (reifiye eşitlikler):
                # Seçilen alternatif ise master ile aynı zamanlarda olacak ve master_dur sabit süreye eşitlenecek.
                model.add(start == ms).only_enforce_if(is_assigned)
                model.add(end == me).only_enforce_if(is_assigned)
                model.add(md == duration).only_enforce_if(is_assigned)

            # Tam olarak bir makine seç
            model.add_exactly_one(assign_literals)  # REPLACED: add_alternative yok, exactly_one + reified

        # Makine içi çakışma kısıtları
        for machine, intervals in machine_to_tasks.items():
            model.add_no_overlap(intervals)

        # Job–Order gruplama
        job_order_map = defaultdict(lambda: defaultdict(list))
        for task in tasks:
            job_order_map[task.job_id][task.order].append(task)

        # Faz geçişleri (master uçları ile)
        for job_id, order_map in job_order_map.items():
            orders = sorted(order_map.keys())
            for i in range(len(orders) - 1):
                current_tasks = order_map[orders[i]]
                next_tasks = order_map[orders[i + 1]]

                current_ends = [master_end[t.id] for t in current_tasks]
                next_starts = [master_start[t.id] for t in next_tasks]

                phase_end = model.new_int_var(0, horizon, f"phase{job_id}_{orders[i]}_end")
                model.add_max_equality(phase_end, current_ends)

                phase_start = model.new_int_var(0, horizon, f"phase{job_id}_{orders[i + 1]}_start")
                model.add_min_equality(phase_start, next_starts)

                model.add(phase_end <= phase_start)

        # Job bitişleri (master end)
        job_final_ends = []
        for job_id, order_map in job_order_map.items():
            if not order_map:
                continue
            last_order = max(order_map.keys())
            last_tasks = order_map[last_order]
            job_end_var = model.new_int_var(0, horizon, f"job_end_{job_id}")
            ends = [master_end[t.id] for t in last_tasks]
            model.add_max_equality(job_end_var, ends)
            job_final_ends.append(job_end_var)

        # Makespan
        makespan = model.new_int_var(0, horizon, "makespan")
        model.add_max_equality(makespan, job_final_ends)

        # İkincil hedef: tüm job'ların toplam bitiş süresi
        total_job_completion = model.new_int_var(0, horizon * max(1, len(job_final_ends)), "total_job_completion")
        model.add(total_job_completion == sum(job_final_ends))

        # ---------- LEXICOGRAPHIC 2-AŞAMA ----------
        # Aşama 1: makespan minimize
        self.logger.info("Solver starting... (Stage 1: minimize makespan)")
        solver = cp_model.CpSolver()
        self.logger.info("Solver detailed log starting...")
        solver.parameters.max_time_in_seconds = 60.0
        solver.parameters.log_search_progress = True
        solver.parameters.log_to_stdout = True
        # solver.parameters.num_search_workers = os.cpu_count() or 4

        model.minimize(makespan)
        status1 = solver.solve(model)

        if status1 not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            self.logger.warning("No feasible solution found in Stage 1.")
            raise RuntimeError("No feasible solution found (Stage 1).")

        best_ms = solver.value(makespan)
        self.logger.info(f"Stage 1 | makespan: {best_ms}, status: {solver.StatusName(status1)}, time: {solver.WallTime():.3f}s")

        # Aşama 2: makespan sabit, total_job_completion minimize
        self.logger.info("Solver starting... (Stage 2: minimize total_job_completion with fixed makespan)")
        model.add(makespan == best_ms)
        model.minimize(total_job_completion)
        status2 = solver.solve(model)

        results = []
        self.logger.info(f"Solver Status (Stage 2): {solver.StatusName(status2)}")
        self.logger.debug(f"Wall time (Stage 2): {solver.WallTime():.3f} s")

        if status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
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
            self.logger.warning("No feasible solution found in Stage 2.")
            raise RuntimeError("No feasible solution found (Stage 2).")

        return results
