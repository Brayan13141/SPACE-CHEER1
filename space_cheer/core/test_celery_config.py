# core/test_celery_config.py
"""
F9 (hallazgo 4.5): completar la última task de un job dispara notificaciones
por `.delay()` dentro del ciclo del request. Sin un timeout de conexión al
broker acotado, una caída de Redis convierte esa acción en un cuelgue de
varios minutos para el operario. Estos settings acotan el intento de
conexión para que el `except Exception` de `production/services.py` se
dispare en segundos, no minutos.
"""

from django.conf import settings
from django.test import SimpleTestCase


class CeleryBrokerConnectionTimeoutTests(SimpleTestCase):
    def test_broker_connection_timeout_is_bounded(self):
        timeout = getattr(settings, "CELERY_BROKER_CONNECTION_TIMEOUT", None)
        self.assertIsNotNone(timeout)
        self.assertLessEqual(timeout, 5)

    def test_broker_connection_max_retries_is_bounded(self):
        max_retries = getattr(settings, "CELERY_BROKER_CONNECTION_MAX_RETRIES", None)
        self.assertIsNotNone(max_retries)
        self.assertLessEqual(max_retries, 3)
