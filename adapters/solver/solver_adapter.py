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

    # Eğer `locks` parametresi verilmezse (None gelirse yani), onu boş bir listeye çevirelim.
    def solve(self, tasks: list[TaskInstanceDTO], locks: list | None = None) -> list[PlanResultDTO]:
        locks = locks or []
        # Boş bir oda yaratalım. Tüm problemimizi bu model nesnesinin üzerine çizeceğiz.
        model = cp_model.CpModel()

        # Çözücünün sonsuza kadar arama yapmasını engellemek için bir üst zaman sınırı belirlemeliyiz.
        # En kötü senaryoyu hesaplıyoruz: Her görev, gidebileceği en yavaş makinede, hiç beklemeden peş peşe yapılsa ne kadar sürer?
        # Her task için en büyük uygun süreyi alıp topluyoruz, %50 pay koyup horizon belirliyoruz.
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

        # Buradaki master mantığını ileride unutmamak için not:
        # Bir görevin tek bir takvim çizgisi olduğunu düşün (ana şerit).
        # Bu şerit için tek bir başlangıç ve bitiş var. Görev hangi makinede çalışırsa çalışsın, ana şerit aynı kalır.
        # Makine seçenekleri ise gölgeler gibi: seçilirse ana şeride eşitleniyor, seçilmezse etkisiz.

        self.logger.info("Task-Machine correspondence and its duration:")
        for task in tasks:
            self.logger.info(f"Task: {task.name} ({task.id})")
            durations_map = {}
            # Bu görevin gidebileceği her bir makinedeki süresini bir sözlükte toplayalım.
            for machine in task.machine_candidates:
                d = self.config.get_duration(task.base_name, machine)
                if d and d > 0:
                    durations_map[machine] = d
                else:
                    self.logger.error(f"{machine}'s duration is not found or zero for task {task.name}.")

            if not durations_map: # Eğer bir görev hiçbir makinede çalışamıyorsa, bu problem çözülemez.
                raise ValueError(f"No valid machine durations for task {task.name} ({task.id})")

            # İleriye Not 2: Bir görevi, bir hayalet gibi düşün. Bu hayaletin bir başlangıcı, bir bitişi ve bir süresi var. Ama nerede olduğu belli değil. İşte bu master değişkenler, bu soyut, makineden bağımsız hayalet görevi temsil eder.
            min_d = min(durations_map.values())
            max_d = max(durations_map.values())
            ms = model.new_int_var(0, horizon, f"tstart_{task.id}")
            md = model.new_int_var(min_d, max_d, f"tdur_{task.id}")
            me = model.new_int_var(0, horizon, f"tend_{task.id}")
            mi = model.new_interval_var(ms, md, me, f"tiv_{task.id}") # Bu üçünü birleştirir ve ms + md = me kuralını koyar.

            # # Bu hayalet değişkenleri, ID'leriyle birlikte sözlüklere koyalım.
            master_start[task.id] = ms
            master_dur[task.id]   = md
            master_end[task.id]   = me
            master_interval[task.id] = mi

            # Şimdi her bir makine için bir beden yaratıyoruz. Bu görev, K#1 makinesine girerse ne olur? K#2'ye girerse ne olur? Her bir olasılık, bir opsiyonel bedendir.
            assign_literals = [] # # Her bedenin bir karar düğümü olacak. Bu liste o düğümleri tutar.
            for machine, duration in durations_map.items():
                suffix = f"_{task.id}_{machine}"
                start = model.new_int_var(0, horizon, f"start{suffix}") # # Her bir makine için ayrı bir başlangıç, bitiş ve görev aralığı değişkeni yaratalım.
                end   = model.new_int_var(0, horizon, f"end{suffix}")
                is_assigned = model.new_bool_var(f"assign{suffix}") # İşte bu, o karar düğümü. True ya da False.
                interval = model.new_optional_interval_var(start, duration, end, is_assigned, f"interval{suffix}") # Bu görev aralığı, SADECE is_assigned True ise var olur.

                #  Yarattığımız tüm bu beden parçalarını ve düğümleri sözlüklere kaydedelim.
                interval_vars[(task.id, machine)] = interval
                start_vars[(task.id, machine)]    = start
                end_vars[(task.id, machine)]      = end
                machine_assignments[(task.id, machine)] = is_assigned
                assign_literals.append(is_assigned)

                # Bu potansiyel görevi, NoOverlap kuralı için ilgili makinenin listesine ekleyelim.
                machine_to_tasks.setdefault(machine, []).append(interval)

                # Çözücüye diyoruz ki: "Eğer bir bedeni seçersen (is_assigned True olursa),o bedenin başlangıcı, bitişi ve süresi, o soyut hayaletin başlangıcı, bitişi ve süresine eşit OLMALIDIR."
                model.add(start == ms).only_enforce_if(is_assigned)
                model.add(end   == me).only_enforce_if(is_assigned)
                model.add(md    == duration).only_enforce_if(is_assigned)

            # Kısıt: Her görev için yaratılan tüm bu bedenlerden SADECE BİR TANESİNİ seçebilirsin.
            model.add_exactly_one(assign_literals)

        # Kısıt 1: Bir makinede, aynı anda sadece bir beden olabilir (NoOverlap).
        for machine, intervals in machine_to_tasks.items():
            model.add_no_overlap(intervals)

        # Kısıt 2: Bir işin görevleri doğru sırada yapılmalıdır (Precedence). Hatta inter-precedence da baktık sonra, deftere bak.
        # Görevleri önce job'a, sonra order'a göre grupluyoruz.
        job_order_map = defaultdict(lambda: defaultdict(list))
        for task in tasks:
            job_order_map[task.job_id][task.order].append(task)

        for job_id, order_map in job_order_map.items():
            orders = sorted(order_map.keys())
            for i in range(len(orders) - 1):
                # Bir fazdaki görevlerin hayaletlerinin en son bitişi, bir sonraki fazdaki görevlerin hayaletlerinin en erken başlangıcından önce olmalıdır.
                current_tasks = order_map[orders[i]]
                next_tasks    = order_map[orders[i + 1]]
                current_ends  = [master_end[t.id] for t in current_tasks]
                next_starts   = [master_start[t.id] for t in next_tasks]
                phase_end   = model.new_int_var(0, horizon, f"phase{job_id}_{orders[i]}_end")
                phase_start = model.new_int_var(0, horizon, f"phase{job_id}_{orders[i+1]}_start")
                model.add_max_equality(phase_end, current_ends)
                model.add_min_equality(phase_start, next_starts)
                model.add(phase_end <= phase_start)

        # Ana Amaç: Makespan'i olabildiğince küçültmek. Her bir işin en son görevinin hayaletinin bitiş zamanını buluyoruz.
        job_final_ends = []
        for job_id, order_map in job_order_map.items():
            if not order_map: continue
            last_order = max(order_map.keys())
            last_tasks = order_map[last_order]
            job_end_var = model.new_int_var(0, horizon, f"job_end_{job_id}")
            ends = [master_end[t.id] for t in last_tasks]
            model.add_max_equality(job_end_var, ends)
            job_final_ends.append(job_end_var)

        # makespan, bu son bitişlerin en büyüğüne eşittir.
        makespan = model.new_int_var(0, horizon, "makespan")
        model.add_max_equality(makespan, job_final_ends)

        # İkincil Amaç: Aynı makespan'e sahip çözümler arasında, daha "iyi" olanı seçmek.
        # Daha iyiden kasıt tüm işlerin bitiş zamanlarının toplamı daha küçük olanı istiyoruz.
        # Kısacası, critical path olayı. Yine deftere bakmak gerekebilir burada.
        total_job_completion = model.new_int_var(0, horizon * max(1, len(job_final_ends)), "total_job_completion")
        model.add(total_job_completion == sum(job_final_ends))

        if locks:
            # Eğer kullanıcı belirli görevleri kilitlemek istiyorsa...
            lock_by_tid = { int(l["task_instance_id"]): l for l in locks if "task_instance_id" in l }
            for t in tasks:
                if t.id in lock_by_tid:
                    # O görevin sadece kilitlenen makineye atanmasını (lit = 1) ve diğerlerine atanmamasını (lit = 0) zorunlu kıl.
                    # Ve o görevin hayaletinin başlangıç zamanını sabit bir değere eşitle.
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

        # Aşama 1: Sadece makespan'i minimize et.
        self.logger.info("Solver starting... (Stage 1: minimize makespan)")
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        solver.parameters.log_search_progress = False
        solver.parameters.log_to_stdout = False
        # solver.parameters.num_search_workers = os.cpu_count() or 4

        model.minimize(makespan)
        status1 = solver.solve(model)
        if status1 not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            self.logger.warning("No feasible solution found in Stage 1.")
            raise RuntimeError("No feasible solution found (Stage 1).")

        # Bulunan en iyi makespan değerini bir kenara yaz.
        best_ms = solver.value(makespan)
        self.logger.info(f"Stage 1 | makespan: {best_ms}, status: {solver.StatusName(status1)}, time: {solver.WallTime():.3f}s")

        # Aşama 2: Makespan'i sabitle, şimdi ikincil hedefi minimize et.
        self.logger.info("Solver starting... (Stage 2: minimize total_job_completion with fixed makespan)")
        model.add(makespan == best_ms)
        model.minimize(total_job_completion)
        status2 = solver.solve(model)

        # Burası zaten dökümantasyondan. Deftere bakılabilir ilk günlere.
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
