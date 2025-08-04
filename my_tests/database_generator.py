from datetime import date, timedelta
import random

# Ayarlar
NUM_PACKAGES = 20
MIN_JOBS_PER_PACKAGE = 5
MAX_JOBS_PER_PACKAGE = 8
MIN_TASKS_PER_JOB = 5
MAX_TASKS_PER_JOB = 10

TASK_NAMES = ["kesme", "oyma", "bükme", "yanak açma"]
MACHINE_PREFIXES = {
    "kesme": "K", "oyma": "O", "bükme": "B", "yanak açma": "Y",
}

machine_pool = {
    "K": [f"K#{i}" for i in range(1, 7)],
    "O": [f"O#{i}" for i in range(1, 7)],
    "B": [f"B#{i}" for i in range(1, 7)],
    "Y": [f"Y#{i}" for i in range(1, 7)],
    "D": [f"D#{i}" for i in range(1, 4)],
    "W": [f"W#{i}" for i in range(1, 4)],
    "Z": [f"Z#{i}" for i in range(1, 4)],
    "F": [f"F#{i}" for i in range(1, 4)],
}

# SQL satırları
sql_lines = []
task_id_counter = 1
job_id_counter = 100
today = date.today()

for pkg_id in range(1, NUM_PACKAGES + 1):
    deadline = today + timedelta(days=random.randint(30, 180))
    sql_lines.append(f"-- Package {pkg_id}")
    sql_lines.append(f"INSERT INTO package (package_id, deadline) VALUES ({pkg_id}, '{deadline}');\n")

    num_jobs = random.randint(MIN_JOBS_PER_PACKAGE, MAX_JOBS_PER_PACKAGE)
    for _ in range(num_jobs):
        job_id = job_id_counter
        job_id_counter += 1
        sql_lines.append(f"INSERT INTO job (job_id, package_id) VALUES ({job_id}, {pkg_id});")

        num_tasks = random.randint(MIN_TASKS_PER_JOB, MAX_TASKS_PER_JOB)
        for order in range(1, num_tasks + 1):
            name = random.choice(TASK_NAMES)
            prefix = MACHINE_PREFIXES[name]
            task_type = random.choices(["single", "split"], weights=[0.7, 0.3])[0]
            count = random.randint(2, 3) if task_type == "split" else "NULL"

            sql_lines.append(
                f"INSERT INTO task (task_id, job_id, name, type, order_id, count) "
                f"VALUES ({task_id_counter}, {job_id}, '{name}', '{task_type}', {order}, {count});"
            )

            eligible = random.sample(machine_pool[prefix], k=random.randint(2, len(machine_pool[prefix])))
            for m in eligible:
                sql_lines.append(f"INSERT INTO task_machine (task_id, machine_name) VALUES ({task_id_counter}, '{m}');")

            task_id_counter += 1

# Sonuçları dosyaya yaz (istersen)
with open("generated_sql_data.sql", "w", encoding="utf-8") as f:
    f.write("\n".join(sql_lines))
