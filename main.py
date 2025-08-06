# main.py

import logging

from adapters.driven.plotly_gantt_adapter import render_interactive_gantt
from adapters.driving.json_data_reader_adapter import JsonDataReaderAdapter
from adapters.driving.postgresql_data_reader_adapter import PostgreSQLDataReaderAdapter
from adapters.logging.logger_adapter import LoggerAdapter
from core.ports.fjsm_port import IFJSMCore
from core.ports.logging_port import ILoggingPort
from project_config.machine_config_loader import MachineConfig
from core.fjsm_core import FJSMCore
from adapters.solver.solver_adapter import ORToolsSolver
from adapters.driven.gantt_show_adapter import GanttChartRenderer

def main():

    # Dosya yollarını en başta tanımlıyoruz.
    job_data_path = "json_file.json"
    machine_config_path = "project_config/machine_config.json"
    gantt_output_path = "gantt_chart.png"

    # JSON okuma işini yapacak nesneyi yaratıyoruz. Ona hangi dosyayı okuyacağını söylüyoruz.
    # data_reader = JsonDataReaderAdapter(job_data_path)
    reader = PostgreSQLDataReaderAdapter()
    # Sonrasında dosyanın okunmasını ve içindeki veriyi bizim istediğim DTO şekline çevirmesini sağlıyoruz.
    # packages = data_reader.read_packages()
    packages = reader.read_packages()

    # Makine ve süreleri içeren dosyayı okuyacak nesneyi yaratıp dosyasını veriyoruz.
    machine_config = MachineConfig(machine_config_path)

    # Loglama nesnemizi yaratıyoruz. level sıralaması: CRITICAL > ERROR > WARNING > INFO > DEBUG > NOTSET. Eğer vermezsek default'ı INFO'dur.
    logger : ILoggingPort = LoggerAdapter(level=logging.DEBUG, file_path="logs/fjsm.log")

    # Core nesnesi, FJSM port'unun sözleşmesine uyan bir nesnedir. Dependency injection ile dışarıdan makine listesi ve logger'ı veriyoruz.
    core: IFJSMCore = FJSMCore(machine_config, logger=logger)
    # Core'un task işlerini yapacak metodunu çağırıyoruz.
    task_instances = core.process_packages(packages)

    # Solver'ı da dependency injection ile başlatıyoruz.
    solver = ORToolsSolver(machine_config, logger=logger)
    # Core'dan gelen task listesini solver'a veriyoruz ve sonucu atıyoruz.
    plan_results = solver.solve(task_instances)

    # Gantt grafiğinin çıkacağı nesneyi ve adapter'a gidecek yolu veriyoruz.
    # gantt = GanttChartRenderer(output_path=gantt_output_path, logger = logger)
    # Solver'dan gelen çözümü gantt çizmek için gönderiyoruz.
    # gantt.render(plan_results)

    render_interactive_gantt(plan_results, output_path="gantt_output.html")

    logger.info(f"Plan is done. Gantt chart: {gantt_output_path}")

if __name__ == "__main__":
    main()
