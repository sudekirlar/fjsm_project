# -*- coding: utf-8 -*-
import uuid
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor

from .celery_app import app as celery_app
from .tasks import execute_planning_task
from project_config.settings import POSTGRESQL_CONFIG
from adapters.driving.postgresql_order_writer_adapter import PostgreSQLOrderWriterAdapter

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

# ---------------------------- Solver ----------------------------
@app.route('/api/solver/start', methods=['POST'])
def start_solver_endpoint():
    run_id = uuid.uuid4()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO plan_metadata (run_id, status) VALUES (%s, 'PENDING')", (run_id,))
        conn.commit()
    finally:
        conn.close()
    execute_planning_task.delay(run_id=str(run_id))
    return jsonify({"run_id": str(run_id)})

@app.route('/api/solver/start_with_locks', methods=['POST'])
def start_solver_with_locks_endpoint():
    """
    Body:
    { "locks": [ { "task_instance_id": 123, "machine": "O#3", "start_min": 120 } ] }
    """
    body = request.get_json(force=True, silent=True) or {}
    locks = body.get("locks", [])
    if not isinstance(locks, list):
        return jsonify({"error": "locks must be a list"}), 400
    for lk in locks:
        if not isinstance(lk, dict):
            return jsonify({"error": "invalid lock item"}), 400
        if "task_instance_id" not in lk or "machine" not in lk or "start_min" not in lk:
            return jsonify({"error": "lock requires task_instance_id, machine, start_min"}), 400

    run_id = uuid.uuid4()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO plan_metadata (run_id, status) VALUES (%s, 'PENDING')", (run_id,))
        conn.commit()
    finally:
        conn.close()

    execute_planning_task.delay(run_id=str(run_id), locks=locks)
    return jsonify({"run_id": str(run_id)})

@app.route('/api/solver/status/<run_id>', methods=['GET'])
def get_solver_status_endpoint(run_id):
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
    """
    Son 10 planın id ve label bilgilerini döndürür.
    """
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

    # Frontend için uygun formata çevir
    data = [
        {
            "id": str(r["run_id"]),
            "label": f"Plan #{i+1} - {r['created_at']}"
        }
        for i, r in enumerate(rows)
    ]
    return jsonify(data)

@app.route('/api/plans/<run_id>/gantt', methods=['GET'])
def get_plan_gantt_endpoint(run_id):
    """
    Gantt için yalnızca şu alanları döndürür:
    - task            (task_name)
    - start           (start_time, dakika)
    - finish          (end_time, dakika)
    - resource        (assigned_machine)
    - job_id
    - task_instance_id (opsiyonel, varsa frontend kullanır)

    Not: order_id yok. Tablonuz: plan_results (çoğul) — ekran görüntüsüne göre.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    task_instance_id,
                    job_id,
                    task_name,
                    assigned_machine,
                    start_time,
                    end_time
                FROM plan_result
                WHERE run_id = %s
                ORDER BY start_time ASC
            """, (run_id,))
            rows = cur.fetchall() or []
    finally:
        conn.close()

    gantt_data = [
        {
            "task":     r["task_name"],
            "start":    int(r["start_time"] or 0),
            "finish":   int(r["end_time"] or 0),
            "resource": r["assigned_machine"],
            "job_id":   int(r["job_id"] or 0),
            # Frontend kullanıyorsa işine yarar; kullanmıyorsa görmezden gelir:
            "task_instance_id": int(r["task_instance_id"] or 0),
        }
        for r in rows
    ]
    return jsonify(gantt_data)


# ---------------------------- Orders ----------------------------
@app.route('/api/orders', methods=['POST'])
def create_order_endpoint():
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

        writer = PostgreSQLOrderWriterAdapter()
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
            writer.close()

        return jsonify({"ok": True, "task_id": task_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
