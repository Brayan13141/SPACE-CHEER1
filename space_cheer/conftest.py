import pytest


@pytest.fixture(autouse=True)
def use_simple_static_storage(settings):
    # CompressedManifestStaticFilesStorage requiere collectstatic previo.
    # En tests usamos el backend simple para evitar el error de manifest.
    settings.STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'


@pytest.fixture(autouse=True)
def celery_eager(settings):
    # Ejecuta tasks de Celery síncronamente en el mismo proceso.
    # Evita intentos de conexión a Redis (no disponible en dev local).
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
