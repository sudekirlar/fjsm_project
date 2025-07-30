# main.py

from adapters.driving.json_data_reader_adapter import JsonDataReaderAdapter
from project_config.machine_config_loader import MachineConfig
from core.fjsm_core import FJSMCore
from adapters.solver.solver_adapter import ORToolsSolver
from adapters.driven.gantt_show_adapter import GanttChartRenderer

def main():
    # === 1. Dosya yolları ===
    job_data_path = "json_file.json"
    machine_config_path = "project_config/machine_config.json"
    gantt_output_path = "gantt_chart.png"

    # === 2. Girdi verilerini oku ===
    data_reader = JsonDataReaderAdapter(job_data_path)
    jobs = data_reader.read_jobs()

    # === 3. Makine sürelerini yükle ===
    machine_config = MachineConfig(machine_config_path)

    # === 4. Görevleri üret (split task'leri böl) ===
    core = FJSMCore(machine_config)
    task_instances = core.process_jobs(jobs)

    # === 5. Çözümle ===
    solver = ORToolsSolver(machine_config)
    plan_results = solver.solve(task_instances)

    # === 6. Gantt grafiğini üret ===
    gantt = GanttChartRenderer(output_path=gantt_output_path)
    gantt.render(plan_results)

    print(f"\n✅ Planlama tamamlandı. Gantt grafiği: {gantt_output_path}")


if __name__ == "__main__":
    main()
