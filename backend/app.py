# backend/app.py
import uuid
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor

from .celery_app import app as celery_app
from .tasks import execute_planning_task
from project_config.settings import POSTGRESQL_CONFIG
from adapters.driving.postgresql_order_writer_adapter import PostgreSQLOrderWriterAdapter
import uuid
from pymongo import MongoClient
from backend.database_select import resolve_db_from_request
from adapters.driven.plan_result_writer_adapter import PostgreSQLPlanResultWriter
from adapters.driven.mongo_plan_result_writer_adapter import MongoPlanResultWriter
from adapters.driving.postgresql_order_writer_adapter import PostgreSQLOrderWriterAdapter
from adapters.driving.mongo_order_writer_adapter import MongoOrderWriterAdapter
from project_config.settings import MONGODB_CONFIG

ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173", "*"]

app = Flask(__name__)
app.url_map.strict_slashes = False

CORS(
    app,
    resources={r"/api/*": {"origins": ALLOWED_ORIGINS}},
    supports_credentials=False,
)

def get_db_connection():
    conn = psycopg2.connect(**POSTGRESQL_CONFIG)
    psycopg2.extras.register_uuid(conn_or_curs=conn)
    return conn

@app.after_request
def add_cors_headers(resp):
    origin = request.headers.get("Origin", "*")
    resp.headers["Access-Control-Allow-Origin"] = origin if origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS else "null"
    resp.headers["Vary"] = "Origin"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    req_headers = request.headers.get("Access-Control-Request-Headers", "Content-Type, Authorization")
    resp.headers["Access-Control-Allow-Headers"] = req_headers
    return resp

@app.route("/api/<path:_any>", methods=["OPTIONS"])
def cors_preflight(_any):
    return ("", 204)

def _plan_writer_for(db: str):
    return MongoPlanResultWriter() if db == "MONGO" else PostgreSQLPlanResultWriter()

def _order_writer_for(db: str):
    return MongoOrderWriterAdapter() if db == "MONGO" else PostgreSQLOrderWriterAdapter()


# ---------------------------- Solver ----------------------------
@app.route('/api/solver/start', methods=['POST'])
def start_solver_endpoint():
    db = resolve_db_from_request(request)
    run_id = uuid.uuid4()
    _plan_writer_for(db).create_run_record(run_id)  # PENDING

    # Celery'ye DB tipini de gönder
    execute_planning_task.delay(run_id=str(run_id), db=db)
    return jsonify({"run_id": str(run_id), "db": db})


@app.route('/api/solver/start_with_locks', methods=['POST'])
def start_solver_with_locks_endpoint():
    db = resolve_db_from_request(request)
    body = request.get_json(force=True, silent=True) or {}
    locks = body.get("locks", [])
    if not isinstance(locks, list):
        return jsonify({"error": "locks must be a list"}), 400
    for lk in locks:
        if not isinstance(lk, dict) or not all(k in lk for k in ("task_instance_id","machine","start_min")):
            return jsonify({"error": "lock requires task_instance_id, machine, start_min"}), 400

    run_id = uuid.uuid4()
    _plan_writer_for(db).create_run_record(run_id)
    execute_planning_task.delay(run_id=str(run_id), db=db, locks=locks)
    return jsonify({"run_id": str(run_id), "db": db})


@app.route('/api/solver/status/<run_id>', methods=['GET'])
def get_solver_status_endpoint(run_id):
    db = resolve_db_from_request(request)
    if db == "MONGO":
        cli = MongoClient(MONGODB_CONFIG["uri"])
        meta = cli[MONGODB_CONFIG["db_name"]]["plan_metadata"]
        row = meta.find_one({"run_id": run_id})
        if not row:
            return jsonify({"error": "Plan bulunamadı."}), 404
        return jsonify({
            "state": row.get("status"),
            "makespan": row.get("makespan"),
            "status": row.get("solver_status"),
            "created_at": str(row.get("created_at")),
            "completed_at": str(row.get("completed_at")),
            "error": row.get("error_message")
        })
    else:
        # mevcut PG kodun (senin hali zaten vardı)
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM plan_metadata WHERE run_id = %s", (run_id,))
                run = cur.fetchone()
        finally:
            conn.close()
        if run is None:
            return jsonify({"error": "Plan bulunamadı."}), 404
        return jsonify({
            "state": run.get("status"),
            "makespan": run.get("makespan"),
            "status": run.get("solver_status"),
            "created_at": run.get("created_at"),
            "completed_at": run.get("completed_at"),
            "error": run.get("error_message")
        })


@app.route('/api/plans/<run_id>', methods=['GET'])
def get_plan_info(run_id):
    # opsiyonel bilgi ucu (gerekirse)
    return jsonify({"run_id": run_id})
@app.route('/api/plans/recent', methods=['GET'])
def get_recent_plans():
    db = resolve_db_from_request(request)
    if db == "MONGO":
        cli = MongoClient(MONGODB_CONFIG["uri"])
        meta = cli[MONGODB_CONFIG["db_name"]]["plan_metadata"]
        rows = list(meta.find({}, {"run_id":1, "created_at":1}).sort("created_at", -1).limit(10))
        data = [{"id": str(r.get("run_id")), "label": f"Plan #{i+1} - {r.get('created_at')}"}
                for i, r in enumerate(rows)]
        return jsonify(data)
    else:
        # PG versiyonun (senin halin)
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT run_id, created_at
                    FROM plan_metadata
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                rows = cur.fetchall() or []
        finally:
            conn.close()
        data = [{"id": str(r["run_id"]), "label": f"Plan #{i+1} - {r['created_at']}"} for i, r in enumerate(rows)]
        return jsonify(data)
@app.route('/api/plans/<run_id>/gantt', methods=['GET'])
def get_plan_gantt_endpoint(run_id):
    db = resolve_db_from_request(request)
    if db == "MONGO":
        cli = MongoClient(MONGODB_CONFIG["uri"])
        res = cli[MONGODB_CONFIG["db_name"]]["plan_result"]
        rows = list(res.find({"run_id": run_id}).sort("start_time", 1))
        gantt_data = [{
            "task": r.get("task_name",""),
            "start": int(r.get("start_time",0)),
            "finish": int(r.get("end_time",0)),
            "resource": r.get("assigned_machine",""),
            "job_id": int(r.get("job_id",0)),
            "task_instance_id": int(r.get("task_instance_id",0)),
        } for r in rows]
        return jsonify(gantt_data)
    else:
        # PG versiyonun (mevcut)
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT task_instance_id, job_id, task_name, assigned_machine, start_time, end_time
                    FROM plan_result
                    WHERE run_id = %s
                    ORDER BY start_time ASC
                """, (run_id,))
                rows = cur.fetchall() or []
        finally:
            conn.close()
        gantt_data = [{
            "task": r["task_name"],
            "start": int(r["start_time"] or 0),
            "finish": int(r["end_time"] or 0),
            "resource": r["assigned_machine"],
            "job_id": int(r["job_id"] or 0),
            "task_instance_id": int(r["task_instance_id"] or 0),
        } for r in rows]
        return jsonify(gantt_data)


# ---------------------------- Orders ----------------------------
@app.route('/api/orders', methods=['POST'])
def create_order_endpoint():
    db = resolve_db_from_request(request)  # 👈 seçime göre yaz
    data = request.get_json(force=True, silent=True) or {}
    try:
        package_id = int(data.get("package_id"))
        job_id = int(data.get("job_id"))
        job_type = str(data.get("job_type") or "").strip()
        mode = str(data.get("mode") or "").strip()
        phase = int(data.get("phase"))
        count = data.get("count", None)
        count = int(count) if count is not None else None
        em = data.get("eligible_machines") or []
        deadline = data.get("deadline", 10000)

        if job_type not in {"kesme", "oyma", "bükme", "yanak_açma"}:
            return jsonify({"error": "Geçersiz iş türü."}), 400
        if mode not in {"single", "split"}:
            return jsonify({"error": "Geçersiz mod."}), 400
        if phase < 1:
            return jsonify({"error": "Faz 1 veya daha büyük olmalı."}), 400
        if mode == "split" and (count is None or count < 1):
            return jsonify({"error": "Split modunda count ≥ 1 olmalı."}), 400
        if not isinstance(em, list) or any(not isinstance(x, str) for x in em):
            return jsonify({"error": "eligible_machines listesi hatalı."}), 400

        writer = _order_writer_for(db)  # 👈 router
        try:
            task_id = writer.create_task(
                package_id=package_id,
                job_id=job_id,
                job_type=job_type,
                mode=mode,
                phase=phase,
                count=count,
                eligible_machines=em,
                deadline=deadline,
            )
        finally:
            try: writer.close()
            except: pass

        return jsonify({"ok": True, "task_id": task_id, "db": db})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
