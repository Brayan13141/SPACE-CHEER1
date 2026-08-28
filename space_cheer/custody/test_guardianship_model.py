"""El vínculo de tutela es del par, no del usuario.

Una tutora con dos atletas puede ser madre de una y tutora legal de la otra, y
verificar una de las dos NO acredita la otra. Ese es el defecto que el modelo
anterior no podía representar: `GuardianProfile` colgaba del `User`.
"""

import datetime

import pytest
from django.db.utils import IntegrityError

from custody.models import Guardianship
from orders.tests.factories import UserFactory


@pytest.mark.django_db
class TestGuardianshipModel:

    def _par(self, sufijo):
        atleta = UserFactory(
            username=f"atleta_{sufijo}",
            birth_date=datetime.date.today() - datetime.timedelta(days=365 * 15),
        )
        tutor = UserFactory(
            username=f"tutor_{sufijo}", birth_date=datetime.date(1984, 5, 2),
        )
        return atleta, tutor

    def test_la_tutela_legal_pide_respaldo_y_nace_sin_verificar(self):
        atleta, tutor = self._par("legal")
        vinculo = Guardianship.objects.create(
            athlete=atleta, guardian=tutor, relation=Guardianship.TUTOR,
        )
        assert vinculo.requires_proof is True
        assert vinculo.is_verified is False
        assert vinculo.proof_pending is True

    def test_padre_y_acompanante_no_piden_respaldo(self):
        for i, relacion in enumerate((Guardianship.PADRE, Guardianship.ACOMP)):
            atleta, tutor = self._par(f"sinrespaldo{i}")
            vinculo = Guardianship.objects.create(
                athlete=atleta, guardian=tutor, relation=relacion,
            )
            assert vinculo.requires_proof is False
            assert vinculo.proof_pending is False

    def test_la_relacion_por_defecto_es_acompanante(self):
        atleta, tutor = self._par("default")
        vinculo = Guardianship.objects.create(athlete=atleta, guardian=tutor)
        assert vinculo.relation == Guardianship.ACOMP

    def test_el_mismo_par_no_se_repite(self):
        atleta, tutor = self._par("repetido")
        Guardianship.objects.create(athlete=atleta, guardian=tutor)
        with pytest.raises(IntegrityError):
            Guardianship.objects.create(athlete=atleta, guardian=tutor)

    def test_verificar_un_vinculo_no_acredita_el_otro_del_mismo_tutor(self):
        """El caso que el modelo anterior no podía representar."""
        from django.utils import timezone

        hija, tutora = self._par("hija")
        ajena, _ = self._par("ajena")

        legal = Guardianship.objects.create(
            athlete=ajena, guardian=tutora, relation=Guardianship.TUTOR,
        )
        madre = Guardianship.objects.create(
            athlete=hija, guardian=tutora, relation=Guardianship.PADRE,
        )

        legal.verified_by = UserFactory(username="admin_verifica")
        legal.verified_at = timezone.now()
        legal.save(update_fields=["verified_by", "verified_at"])

        madre.refresh_from_db()
        assert legal.is_verified is True
        assert madre.is_verified is False

    def test_el_aviso_de_carga_cuenta_los_vinculos_del_tutor(self):
        _, tutora = self._par("carga")
        for i in range(Guardianship.SOFT_ATHLETE_LIMIT):
            atleta, _ = self._par(f"carga{i}")
            vinculo = Guardianship.objects.create(athlete=atleta, guardian=tutora)
        assert Guardianship.athlete_count_for(tutora) == Guardianship.SOFT_ATHLETE_LIMIT
        assert vinculo.over_soft_limit is False

        uno_mas, _ = self._par("carga_extra")
        extra = Guardianship.objects.create(athlete=uno_mas, guardian=tutora)
        assert extra.over_soft_limit is True

    def test_borrar_al_atleta_borra_el_vinculo(self):
        atleta, tutor = self._par("cascade")
        Guardianship.objects.create(athlete=atleta, guardian=tutor)
        atleta.delete()
        assert Guardianship.objects.count() == 0