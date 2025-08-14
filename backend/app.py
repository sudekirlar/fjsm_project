# backend/app.py:

import uuid
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor

# Kendi celery app ve task objelerini import et
from .celery_app import app as celery_app
from .tasks import execute_planning_task
from project_config.settings import POSTGRESQL_CONFIG

app = Flask(__name__)
# Frontend portunu dinlemek için önemli.
CORS(app)


def get_db_connection():
    """Veritabanı bağlantısı için yardımcı fonksiyon."""
    conn = psycopg2.connect(**POSTGRESQL_CONFIG)
    # UUID'lerin doğru okunması için önemli.
    psycopg2.extras.register_uuid(conn_or_curs=conn)
    return conn

@app.route('/api/solver/start', methods=['POST'])
def start_solver_endpoint():
    # Start butonuna tıklandıktan sonra
    run_id = uuid.uuid4()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO plan_metadata (run_id, status) VALUES (%s, 'PENDING')", (run_id,))
        conn.commit()
    finally:
        conn.close()

    # Celery görevini bu ID ile arka planda çalışması için tetikliyoruz.
    execute_planning_task.delay(run_id=str(run_id))

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

    # Frontend'in beklediği formata uygun bir cevap oluşturalım
    response_data = {
        "state": run.get("status"),
        "makespan": run.get("makespan"),
        "status": run.get("solver_status"),
        "created_at": run.get("created_at"),
        "completed_at": run.get("completed_at"),
        "error": run.get("error_message")
    }
    return jsonify(response_data)

@app.route('/api/plans/<run_id>/gantt', methods=['GET'])
def get_plan_gantt_endpoint(run_id):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM plan_result WHERE run_id = %s ORDER BY start_time", (run_id,))
            results = cur.fetchall()
    finally:
        conn.close()

    # Gantt bilgilerini gönderiyoruz.
    gantt_data = [
        {
            "task": result["task_name"],
            "start": result["start_time"],
            "finish": result["end_time"],
            "resource": result["assigned_machine"],
            "job_id": result["job_id"]
        } for result in results
    ]
    return jsonify(gantt_data)


# Diğer işlevler eklenecek.

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)