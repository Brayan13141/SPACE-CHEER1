import pytest


@pytest.fixture(autouse=True)
def use_simple_static_storage(settings):
    # CompressedManifestStaticFilesStorage requiere collectstatic previo.
    # En tests usamos el backend simple para evitar el error de manifest.
    settings.STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
