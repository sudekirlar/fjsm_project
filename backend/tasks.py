# backend/tasks.py

import logging
from .celery_app import app
from adapters.driven.plan_result_writer_adapter import PostgreSQLPlanResultWriter
from adapters.driven.mongo_plan_result_writer_adapter import MongoPlanResultWriter
from adapters.driving.postgresql_data_reader_adapter import PostgreSQLReaderAdapter
from adapters.driving.mongo_data_reader_adapter import MongoReaderAdapter
from adapters.logging.logger_adapter import LoggerAdapter
from config.machine_config_loader import MachineConfig
from core.fjsm_core import FJSMCore
from adapters.solver.solver_adapter import ORToolsSolver

def _get_io(db: str):
    db = (db or "PG").upper()
    if db == "MONGO":
        return MongoReaderAdapter(), MongoPlanResultWriter()
    return PostgreSQLReaderAdapter(), PostgreSQLPlanResultWriter()

# Burada name genel ad, terminalde bu yazacak. bind da Celery'e fonksiyonu çağırırken ilk argüman self al diyoruz.
@app.task(name='backend.tasks.execute_planning_task', bind=True)
def execute_planning_task(self, *args, **kwargs): # args argümanları tuple toplar, kwargs anahtar kelimeleri tuple toplar.
    # run_id'yi arıyoruz nerede? Pop ile de siliyoruz.
    run_id = kwargs.pop("run_id", None) or (args[0] if args else None)
    db     = (kwargs.pop("db", None) or "PG").upper()
    locks  = kwargs.pop("locks", None) or (args[1] if len(args) > 1 else None)
    if run_id is None:
        raise ValueError("run_id is required")

    # Daha öncesinde main'de olan wiring'lerimiz.
    logger = LoggerAdapter(level=logging.DEBUG)
    reader, result_writer = _get_io(db)

    logger.info(f"Task started for run_id: {run_id} (DB={db})")
    try:
        result_writer.update_run_status(run_id, 'RUNNING')

        machine_config = MachineConfig("config/machine_config.json")
        packages = reader.read_packages()

        core = FJSMCore(machine_config, logger=logger)
        task_instances = core.process_packages(packages)

        solver = ORToolsSolver(machine_config, logger=logger)
        plan_results = solver.solve(task_instances, locks=locks or [])

        result_writer.write_results(run_id, plan_results)
        makespan = max((r.end_time for r in plan_results), default=0)
        result_writer.update_run_status(run_id, 'COMPLETED', makespan=makespan, solver_status="OPTIMAL")

        logger.info(f"Task completed successfully for run_id: {run_id}")
        return {'status': 'COMPLETED', 'makespan': makespan}

    except Exception as e:
        logger.error(f"Task failed for run_id: {run_id}. Error: {e}", exc_info=True)
        result_writer.update_run_status(run_id, 'FAILED', error_message=str(e))
        raise
