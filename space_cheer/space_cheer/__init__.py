# space_cheer/__init__.py

# Asegura que Celery se carga cuando Django inicia
from .celery import app as celery_app

__all__ = ("celery_app",)
