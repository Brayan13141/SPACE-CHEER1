import pytest
from django.core.exceptions import ValidationError

from measures.models import AthleteStandardSize
from orders.tests.factories import AthleteFactory


@pytest.mark.django_db
class TestAthleteStandardSize:

    def test_guarda_la_talla_de_un_alumno(self):
        athlete = AthleteFactory()

        size = AthleteStandardSize.objects.create(user=athlete, size="M")

        assert athlete.standard_size == size
        assert size.updated_at is not None

    def test_rechaza_una_talla_fuera_de_la_escala(self):
        athlete = AthleteFactory()

        size = AthleteStandardSize(user=athlete, size="26")

        with pytest.raises(ValidationError):
            size.full_clean()

    def test_sin_talla_capturada_no_hay_fila(self):
        athlete = AthleteFactory()

        assert not AthleteStandardSize.objects.filter(user=athlete).exists()
