# backend/celery_app.py
from celery import Celery

app = Celery(
    'backend', # Celery app'imin ismi.
    broker='redis://localhost:6379/0', # Celery'nin postane olarak kullandığı yerin adresi. Flask, Celery'e mektup buraya bırakır, Celery de hep burayı dinler. Redis'in 0 numaralı sunucusu diyoruz.
    backend='redis://localhost:6379/0', # Sonuç deposu direkt.
    include=['backend.tasks'], # Celery, tasks.py'ı otomatik import eder. Tüm fonksiyonları almış olur.
)

app.conf.update( # Benim haberleşmem JSON yoluyla, onları tanımladım.
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Istanbul',
    enable_utc=True,
)
