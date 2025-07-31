from ortools.sat.python import cp_model
from core.models.data_model import TaskInstanceDTO, PlanResultDTO
from project_config.machine_config_loader import MachineConfig
from collections import defaultdict, Counter


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

        print("🔧 Görev–Makine eşleşmeleri ve süreler:")
        for task in tasks:
            print(f"📌 Görev: {task.name} ({task.id})")
            for machine in task.machine_candidates:
                duration = self.config.get_duration(task.base_name, machine)
                if duration is None:
                    print(f"   🚫 {machine} için süre bulunamadı!")
                    continue

                print(f"   ✅ {machine} → {duration} birim süre")
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

            model.add(sum(machine_assignments[task.id, m] for m in task.machine_candidates) == 1)

        for machine, intervals in machine_to_tasks.items():
            model.add_no_overlap(intervals)

        job_order_map = defaultdict(lambda: defaultdict(list))
        for task in tasks:
            job_order_map[task.job_id][task.order].append(task)

        for job_id, order_map in job_order_map.items():
            orders = sorted(order_map.keys())
            for i in range(len(orders) - 1):
                current_tasks = order_map[orders[i]]
                next_tasks = order_map[orders[i + 1]]

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

        all_ends = [end_vars[task.id, m] for task in tasks for m in task.machine_candidates]
        makespan = model.new_int_var(0, horizon, "makespan")
        model.add_max_equality(makespan, all_ends)
        model.minimize(makespan)

        print("\n🚀 Çözüm başlatılıyor...")
        solver = cp_model.CpSolver()
        status = solver.solve(model)

        results = []

        print(f"\n📊 Çözüm Durumu: {solver.StatusName(status)}")
        print(f"⏱️  Wall time: {solver.WallTime():.3f} saniye")

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
                            end_time=end
                        ))
                        print(f"   ✅ {task.name} ({task.job_id}) → {machine} | {start} → {end}")
                        assignment_counter[machine] += 1
                        assigned_task_ids.add(task.id)
                        break

            unassigned_ids = {t.id for t in tasks} - assigned_task_ids
            if unassigned_ids:
                print(f"\n⚠️  {len(unassigned_ids)} görev atanamadı: {sorted(unassigned_ids)}")

            print("\n🧮 Makineye göre görev sayısı:")
            for machine, count in assignment_counter.items():
                print(f"   • {machine}: {count} görev")

            print(f"\n📦 Toplam görev: {len(tasks)} / Atanan: {len(results)}")

        else:
            raise RuntimeError("No feasible solution found.")

        return results
