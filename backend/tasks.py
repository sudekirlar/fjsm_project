# backend/tasks.py
import logging
# Göreceli import yaparak celery'nin app'inin nerede olduğunu söylüyoruz.
from .celery_app import app
from adapters.driven.plan_result_writer_adapter import PostgreSQLPlanResultWriter
from adapters.driving.postgresql_data_reader_adapter import PostgreSQLReaderAdapter
from adapters.driving.mongo_data_reader_adapter import MongoReaderAdapter
from adapters.logging.logger_adapter import LoggerAdapter
from project_config.machine_config_loader import MachineConfig
from core.fjsm_core import FJSMCore
from adapters.solver.solver_adapter import ORToolsSolver
from services.database_assembler import PGMangoAssembler


@app.task(name='backend.tasks.execute_planning_task', bind=True)
def execute_planning_task(self, run_id: str):
    # main'deki wiring'i aldım.
    logger = LoggerAdapter(level=logging.DEBUG)
    result_writer = PostgreSQLPlanResultWriter()

    logger.info(f"Task started for run_id: {run_id}")

    try:
        result_writer.update_run_status(run_id, 'RUNNING')

        machine_config = MachineConfig("project_config/machine_config.json")
        pg_adapter = PostgreSQLReaderAdapter()
        mongo_adapter = MongoReaderAdapter()
        assembler = PGMangoAssembler(repos={"pg": pg_adapter, "mongo": mongo_adapter})
        packages = assembler.read_all()

        core = FJSMCore(machine_config, logger=logger)
        task_instances = core.process_packages(packages)

        solver = ORToolsSolver(machine_config, logger=logger)


        plan_results = solver.solve(task_instances)


        result_writer.write_results(run_id, plan_results)


        makespan = max(r.end_time for r in plan_results) if plan_results else 0

        # Solver Status'u çekeceğiz sonra.
        result_writer.update_run_status(run_id, 'COMPLETED', makespan=makespan, solver_status="OPTIMAL_OR_FEASIBLE")

        logger.info(f"Task completed successfully for run_id: {run_id}")
        return {'status': 'COMPLETED', 'makespan': makespan}

    except Exception as e:
        logger.error(f"Task failed for run_id: {run_id}. Error: {e}", exc_info=True)
        result_writer.update_run_status(run_id, 'FAILED', error_message=str(e))
        raise