# backend/celery_app.py
from celery import Celery

# Adı app yaptık.
app = Celery(
    'backend',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=['backend.tasks'],  # görev modülünü yüklet
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Istanbul',
    enable_utc=True,
)
