import pytest

from accounts.models import PiiAccessLog


@pytest.mark.django_db
class TestSizeAccessTypes:

    def test_los_tipos_de_acceso_a_talla_existen(self):
        codes = {code for code, _ in PiiAccessLog.ACCESS_TYPES}

        assert "VIEW_SIZE" in codes
        assert "EDIT_SIZE" in codes
