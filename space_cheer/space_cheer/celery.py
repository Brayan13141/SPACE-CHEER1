# space_cheer/celery.py

import os
from celery import Celery
from celery.schedules import crontab

# Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "space_cheer.settings")

# Celery app instance
app = Celery("space_cheer")

# Load config from Django settings (CELERY_* variables)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Optional: Custom beat schedule (puedes definirlo aquí o en settings.py)
app.conf.beat_schedule = {
    "auto-close-measurements-daily": {
        "task": "orders.tasks.auto_close_measurements",
        "schedule": crontab(hour=0, minute=5),  # 00:05 AM diario
        "options": {
            "expires": 3600,  # Expira si no se ejecuta en 1 hora
        },
    },
}

# Timezone
app.conf.timezone = "UTC"


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tarea de debug para verificar que Celery funciona"""
    print(f"Request: {self.request!r}")
