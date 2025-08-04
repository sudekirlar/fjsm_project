# denemelerim/fjsm_problem_deneme.py
# import collections
# from ortools.sat.python import cp_model
#
# def fjsm_problem():
#     jobs_data = [
#         [("kesme" , 5) , ("dövme" , 3)],   #iş 0
#         [("oyma" , 4) , ("bükme" , 2) , ("kesme" , 4)]  #iş 1
#     ]
#
#     machine_resources = {
#         "kesme" : [0 , 1],  # kesme key'ine ID olarak 0 ve 1 atandı.
#         "oyma" : [2],       # oyma key'ine ID olarak 2 atandı.
#         "bükme" : [3],       # bükme key'ine ID olarak 3 atandı.
#         "dövme" : [4]
#     }
#
#     #num_jobs = len(jobs_data)   # num_jobs içinde kaç iş var = 2
#     #all_jobs = range(num_jobs)  # all_jobs bunlara ID atıyor = [0, 1]
#
#     all_machines = []
#     for m_type in machine_resources:
#         all_machines.extend(machine_resources[m_type])  # extend makineleri tek bir listeye alır, append'ten farklıdır, aslında iki listeyi birleştirir gibi düşün.
#
#     #num_machines = len(all_machines)
#
#     horizon = sum(task[1] for job in jobs_data for task in job)     # burada task[1] alınıyor, maksat int duration'Ları almak, task[0] dersen string almış olursun.
#
#     #horizon = 0
#     #for job in jobs_data:
#         #for task in job:
#             #horizon += task[1]
#
#     model = cp_model.CpModel()
#
#     all_tasks = {}
#
#     # get_var_by_name olmadığı için start_vars ve end_vars tanımlıyorum. (CPSAT'ta yok)
#     start_vars = {}
#     end_vars = {}
#
#     for job_id, job in enumerate(jobs_data):
#         for task_id, task in enumerate(job):
#             suffix = f"_{task_id}_{job_id}"
#             start_var = model.new_int_var(0, horizon, "start" + suffix)
#             end_var = model.new_int_var(0, horizon, "end" + suffix)
#             start_vars[job_id, task_id] = start_var
#             end_vars[job_id, task_id] = end_var
#
#     assignment_bools = {}
#     for job_id, job in enumerate(jobs_data):
#         for task_id, task in enumerate(job):
#             machine_type, duration = task
#             literals = []
#             for machine_id in machine_resources[machine_type]:
#                 l = model.new_bool_var(f"is_assigned_to_{job_id}_{task_id}_to_{machine_id}")
#                 assignment_bools[(job_id, task_id, machine_id)] = l
#                 literals.append(l)
#                 interval = model.new_optional_interval_var(start_vars[job_id, task_id], duration, end_vars[job_id, task_id], l, f"interval_{job_id}_{task_id}_on_{machine_id}")
#                 all_tasks[(job_id, task_id, machine_id)] = interval
#             model.add_exactly_one(literals)  # Yeri daha sonra kontrol edilecek.
#
#     # KURAL 1: NO OVERLAP KURALI VE ZAMAN ÇİZGİLERİNİN OLUŞTURULMASI (ZAMAN ÇİZGİLERİNİN KENDİ ARASINDA ÇAKIŞMA YAŞAMAMASI)
#     for machine_id in all_machines:
#         intervals_on_machine = []
#         for job_id, job in enumerate(jobs_data):
#             for task_id, task in enumerate(job):
#                 if(job_id, task_id, machine_id) in all_tasks:
#                     intervals_on_machine.append(all_tasks[(job_id, task_id, machine_id)])
#
#         model.add_no_overlap(intervals_on_machine)
#
#     # KURAL 2: BİR SONRAKİ İŞİN BAŞLANGIÇ ZAMANININ ŞİMDİKİNİN BİTİŞİNDEN BÜYÜK VEYA EŞİT OLMASI
#     for job_id, job in enumerate(jobs_data):
#         for task_id in range(len(job) - 1):
#             model.add(start_vars[job_id, task_id + 1] >= end_vars[job_id, task_id])
#
#     makespan = model.new_int_var(0, horizon, "makespan")
#     last_task_ends = []
#     for job_id, job in enumerate(jobs_data):
#         last_task_id = len(job) -1
#         last_task_ends.append(end_vars[job_id , last_task_id])
#
#     model.add_max_equality(makespan, last_task_ends)
#     model.minimize(makespan)
#
#     solver = cp_model.CpSolver()
#     status = solver.Solve(model)
#
#     if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
#         print("The solution is found.")
#         print(f"Optimal makespan: {solver.ObjectiveValue()}")
#         print(f"Solution time: {solver.wall_time :.2f} seconds.")
#         for job_id, job in enumerate(jobs_data):
#             print(f"Job: {job_id}")
#             for task_id, task in enumerate(job):
#                 machine_type, _ = task
#                 for machine_id in machine_resources[machine_type]:
#                     assigned = assignment_bools[(job_id, task_id, machine_id)]
#                     if solver.BooleanValue(assigned):
#                         start = solver.Value(start_vars[job_id, task_id])
#                         end = solver.Value(end_vars[job_id, task_id])
#                         print(
#                             f"Operation task: {task_id} and machine name: {machine_type} assigned to {job_id} {task_id} to {machine_id} | Start: {start}, End: {end}")
#                         break
#     else:
#         print("The solution is NOT found.")
#
# fjsm_problem()
