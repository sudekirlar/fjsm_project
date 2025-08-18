# adapters/solver/solver_adapter

import os
from ortools.sat.python import cp_model
from core.models.data_model import TaskInstanceDTO, PlanResultDTO
from core.ports.logging_port import ILoggingPort
from config.machine_config_loader import MachineConfig
from collections import defaultdict, Counter

class ORToolsSolver:
    def __init__(self, machine_config: MachineConfig, logger: ILoggingPort):
        self.config = machine_config
        self.logger = logger

    def solve(self, tasks: list[TaskInstanceDTO], locks: list | None = None) -> list[PlanResultDTO]:
        locks = locks or []
        model = cp_model.CpModel()

        max_duration_sum = 0
        for task in tasks:
            durations = [
                self.config.get_duration(task.base_name, m)
                for m in task.machine_candidates
                if self.config.get_duration(task.base_name, m) > 0
            ]
            if durations:
                max_duration_sum += max(durations)
        horizon = int(max_duration_sum * 1.5)

        start_vars = {}
        end_vars = {}
        interval_vars = {}
        machine_assignments = {}
        machine_to_tasks = {}
        master_start = {}
        master_dur = {}
        master_end = {}
        master_interval = {}

        self.logger.info("Task-Machine correspondence and its duration:")
        for task in tasks:
            self.logger.info(f"Task: {task.name} ({task.id})")
            durations_map = {}
            for machine in task.machine_candidates:
                d = self.config.get_duration(task.base_name, machine)
                if d and d > 0:
                    durations_map[machine] = d
                else:
                    self.logger.error(f"{machine}'s duration is not found or zero for task {task.name}.")

            if not durations_map:
                raise ValueError(f"No valid machine durations for task {task.name} ({task.id})")

            min_d = min(durations_map.values())
            max_d = max(durations_map.values())
            ms = model.new_int_var(0, horizon, f"tstart_{task.id}")
            md = model.new_int_var(min_d, max_d, f"tdur_{task.id}")
            me = model.new_int_var(0, horizon, f"tend_{task.id}")
            mi = model.new_interval_var(ms, md, me, f"tiv_{task.id}")

            master_start[task.id] = ms
            master_dur[task.id]   = md
            master_end[task.id]   = me
            master_interval[task.id] = mi

            assign_literals = []
            for machine, duration in durations_map.items():
                suffix = f"_{task.id}_{machine}"
                start = model.new_int_var(0, horizon, f"start{suffix}")
                end   = model.new_int_var(0, horizon, f"end{suffix}")
                is_assigned = model.new_bool_var(f"assign{suffix}")
                interval = model.new_optional_interval_var(start, duration, end, is_assigned, f"interval{suffix}")

                interval_vars[(task.id, machine)] = interval
                start_vars[(task.id, machine)]    = start
                end_vars[(task.id, machine)]      = end
                machine_assignments[(task.id, machine)] = is_assigned
                assign_literals.append(is_assigned)

                machine_to_tasks.setdefault(machine, []).append(interval)

                model.add(start == ms).only_enforce_if(is_assigned)
                model.add(end   == me).only_enforce_if(is_assigned)
                model.add(md    == duration).only_enforce_if(is_assigned)

            model.add_exactly_one(assign_literals)

        # NoOverlap per machine
        for machine, intervals in machine_to_tasks.items():
            model.add_no_overlap(intervals)

        job_order_map = defaultdict(lambda: defaultdict(list))
        for task in tasks:
            job_order_map[task.job_id][task.order].append(task)

        for job_id, order_map in job_order_map.items():
            orders = sorted(order_map.keys())
            for i in range(len(orders) - 1):
                current_tasks = order_map[orders[i]]
                next_tasks    = order_map[orders[i + 1]]
                current_ends  = [master_end[t.id] for t in current_tasks]
                next_starts   = [master_start[t.id] for t in next_tasks]
                phase_end   = model.new_int_var(0, horizon, f"phase{job_id}_{orders[i]}_end")
                phase_start = model.new_int_var(0, horizon, f"phase{job_id}_{orders[i+1]}_start")
                model.add_max_equality(phase_end, current_ends)
                model.add_min_equality(phase_start, next_starts)
                model.add(phase_end <= phase_start)

        job_final_ends = []
        for job_id, order_map in job_order_map.items():
            if not order_map: continue
            last_order = max(order_map.keys())
            last_tasks = order_map[last_order]
            job_end_var = model.new_int_var(0, horizon, f"job_end_{job_id}")
            ends = [master_end[t.id] for t in last_tasks]
            model.add_max_equality(job_end_var, ends)
            job_final_ends.append(job_end_var)

        makespan = model.new_int_var(0, horizon, "makespan")
        model.add_max_equality(makespan, job_final_ends)
        total_job_completion = model.new_int_var(0, horizon * max(1, len(job_final_ends)), "total_job_completion")
        model.add(total_job_completion == sum(job_final_ends))

        if locks:
            lock_by_tid = { int(l["task_instance_id"]): l for l in locks if "task_instance_id" in l }
            for t in tasks:
                if t.id in lock_by_tid:
                    lk = lock_by_tid[t.id]
                    m  = str(lk["machine"])
                    s  = int(lk["start_min"])
                    if (t.id, m) not in machine_assignments:
                        raise ValueError(f"Lock refers to invalid machine '{m}' for task {t.id}")
                    for mc in t.machine_candidates:
                        if (t.id, mc) not in machine_assignments:
                            continue
                        lit = machine_assignments[(t.id, mc)]
                        if mc == m:
                            model.add(lit == 1)
                        else:
                            model.add(lit == 0)
                    model.add(master_start[t.id] == s)

        self.logger.info("Solver starting... (Stage 1: minimize makespan)")
        solver = cp_model.CpSolver()
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

        self.logger.info("Solver starting... (Stage 2: minimize total_job_completion with fixed makespan)")
        model.add(makespan == best_ms)
        model.minimize(total_job_completion)
        status2 = solver.solve(model)

        results = []
        self.logger.info(f"Solver Status (Stage 2): {solver.StatusName(status2)}")
        if status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            assignment_counter = Counter()
            assigned_task_ids = set()
            for task in tasks:
                for machine in task.machine_candidates:
                    key = (task.id, machine)
                    if key in machine_assignments and solver.boolean_value(machine_assignments[key]):
                        start = solver.value(start_vars[key])
                        end   = solver.value(end_vars[key])
                        results.append(PlanResultDTO(
                            task_instance_id=task.id,
                            job_id=task.job_id,
                            task_name=task.name,
                            assigned_machine=machine,
                            start_time=start,
                            end_time=end,
                            package_uid=task.package_uid,
                        ))
                        assignment_counter[machine] += 1
                        assigned_task_ids.add(task.id)
                        break
            unassigned_ids = {t.id for t in tasks} - assigned_task_ids
            if unassigned_ids:
                self.logger.error(f"{len(unassigned_ids)} task did not assigned: {sorted(unassigned_ids)}")
            self.logger.debug("Machine assignments:")
            for machine, count in assignment_counter.items():
                self.logger.debug(f"{machine}: {count} task")
            self.logger.debug(f"All tasks count: {len(tasks)} / Assigned: {len(results)}")
        else:
            self.logger.warning("No feasible solution found in Stage 2.")
            raise RuntimeError("No feasible solution found (Stage 2).")

        return results
