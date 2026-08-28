"""Los criterios que el modelo de un solo tutor hacía imposibles.

1. Un menor con dos tutores: los dos son tutores de pleno derecho.
2. Una tutora con dos atletas, TUTOR verificada en una y PADRE en la otra.
6. Quitar un vínculo no toca los demás, ni del atleta ni del tutor.
"""

import datetime

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from accounts.models import AthleteProfile, Role, UserOwnership
from custody.models import Guardianship
from custody.services.minor_service import MinorAthleteService
from orders.tests.factories import UserFactory


@pytest.mark.django_db
class TestVariosTutores:

    def setup_method(self):
        self.admin_role, _ = Role.objects.get_or_create(name="ADMIN")
        self.guardian_role, _ = Role.objects.get_or_create(name="GUARDIAN")
        self.admin = UserFactory(
            username="admin_multi", birth_date=datetime.date(1985, 1, 1),
        )
        self.admin.roles.add(self.admin_role)

    def _menor(self, username):
        menor = UserFactory(
            username=username,
            birth_date=datetime.date.today() - datetime.timedelta(days=365 * 15),
        )
        # update_or_create y no create: si alguien le agrega el rol ATHLETE a
        # este helper, el signal de accounts ya habrá creado el perfil.
        AthleteProfile.objects.update_or_create(
            user=menor, defaults={"emergency_contact": "Familia"},
        )
        return menor

    def _tutor(self, username):
        tutor = UserFactory(username=username, birth_date=datetime.date(1984, 5, 2))
        tutor.roles.add(self.guardian_role)
        return tutor

    # ── 1. un menor, dos tutores ────────────────────────────────────
    def test_un_menor_puede_tener_dos_tutores(self):
        menor = self._menor("hija_dos_tutores")
        madre = self._tutor("madre_dos")
        padre = self._tutor("padre_dos")

        MinorAthleteService.assign_guardian(
            athlete=menor, guardian=madre, assigned_by=self.admin,
            relation=Guardianship.PADRE,
        )
        MinorAthleteService.assign_guardian(
            athlete=menor, guardian=padre, assigned_by=self.admin,
            relation=Guardianship.PADRE,
        )

        assert MinorAthleteService.is_guardian_of(madre, menor) is True
        assert MinorAthleteService.is_guardian_of(padre, menor) is True
        assert set(MinorAthleteService.get_guardians(menor)) == {madre, padre}
        assert MinorAthleteService.requires_guardian(menor) is False

    def test_asignar_dos_veces_al_mismo_tutor_actualiza_la_relacion(self):
        """Idempotente: la segunda alta no duplica el vínculo."""
        menor = self._menor("hija_idem")
        madre = self._tutor("madre_idem")

        MinorAthleteService.assign_guardian(
            athlete=menor, guardian=madre, assigned_by=self.admin,
            relation=Guardianship.ACOMP,
        )
        vinculo = MinorAthleteService.assign_guardian(
            athlete=menor, guardian=madre, assigned_by=self.admin,
            relation=Guardianship.PADRE,
        )

        assert Guardianship.objects.filter(athlete=menor).count() == 1
        assert vinculo.relation == Guardianship.PADRE

    def test_un_adulto_ajeno_no_es_tutor(self):
        menor = self._menor("hija_ajena")
        madre = self._tutor("madre_ajena")
        ajeno = self._tutor("ajeno")
        MinorAthleteService.assign_guardian(
            athlete=menor, guardian=madre, assigned_by=self.admin,
        )
        assert MinorAthleteService.is_guardian_of(ajeno, menor) is False

    # ── 2. una tutora, dos atletas, verificación independiente ──────
    def test_verificar_un_vinculo_no_acredita_el_otro(self):
        """El defecto vivo que este trabajo cierra."""
        hija = self._menor("hija_propia")
        ajena = self._menor("ajena_tutelada")
        tutora = self._tutor("tutora_dos_atletas")

        como_madre = MinorAthleteService.assign_guardian(
            athlete=hija, guardian=tutora, assigned_by=self.admin,
            relation=Guardianship.PADRE,
        )
        como_tutora = MinorAthleteService.assign_guardian(
            athlete=ajena, guardian=tutora, assigned_by=self.admin,
            relation=Guardianship.TUTOR,
        )

        MinorAthleteService.verify_guardianship(
            guardianship=como_tutora, verified_by=self.admin,
            legal_document="Acta 1234/2026",
        )

        como_tutora.refresh_from_db()
        como_madre.refresh_from_db()
        assert como_tutora.is_verified is True
        assert como_madre.is_verified is False
        assert como_madre.relation == Guardianship.PADRE

    def test_cambiar_la_relacion_invalida_solo_ese_vinculo(self):
        hija = self._menor("hija_rel")
        ajena = self._menor("ajena_rel")
        tutora = self._tutor("tutora_rel")

        uno = MinorAthleteService.assign_guardian(
            athlete=hija, guardian=tutora, assigned_by=self.admin,
            relation=Guardianship.TUTOR,
        )
        otro = MinorAthleteService.assign_guardian(
            athlete=ajena, guardian=tutora, assigned_by=self.admin,
            relation=Guardianship.TUTOR,
        )
        MinorAthleteService.verify_guardianship(
            guardianship=uno, verified_by=self.admin, legal_document="Acta A",
        )
        MinorAthleteService.verify_guardianship(
            guardianship=otro, verified_by=self.admin, legal_document="Acta B",
        )

        MinorAthleteService.update_guardian_relation(
            athlete=hija, guardian=tutora,
            relation=Guardianship.PADRE, updated_by=self.admin,
        )

        uno.refresh_from_db()
        otro.refresh_from_db()
        assert uno.is_verified is False
        assert uno.legal_document == ""
        assert otro.is_verified is True
        assert otro.legal_document == "Acta B"

    # ── 6. quitar un vínculo no toca los demás ──────────────────────
    def test_quitar_un_tutor_deja_intacto_al_otro(self):
        menor = self._menor("hija_baja")
        madre = self._tutor("madre_baja")
        padre = self._tutor("padre_baja")
        MinorAthleteService.assign_guardian(
            athlete=menor, guardian=madre, assigned_by=self.admin,
        )
        MinorAthleteService.assign_guardian(
            athlete=menor, guardian=padre, assigned_by=self.admin,
        )

        MinorAthleteService.remove_guardian(
            athlete=menor, guardian=padre, removed_by=self.admin,
        )

        assert MinorAthleteService.is_guardian_of(madre, menor) is True
        assert MinorAthleteService.is_guardian_of(padre, menor) is False

    def test_quitar_un_vinculo_no_toca_los_otros_atletas_del_tutor(self):
        hija = self._menor("hija_otro")
        ajena = self._menor("ajena_otro")
        tutora = self._tutor("tutora_otro")
        otra_tutora = self._tutor("otra_tutora")
        MinorAthleteService.assign_guardian(
            athlete=hija, guardian=tutora, assigned_by=self.admin,
        )
        MinorAthleteService.assign_guardian(
            athlete=ajena, guardian=tutora, assigned_by=self.admin,
        )
        MinorAthleteService.assign_guardian(
            athlete=hija, guardian=otra_tutora, assigned_by=self.admin,
        )

        MinorAthleteService.remove_guardian(
            athlete=hija, guardian=tutora, removed_by=self.admin,
        )

        assert MinorAthleteService.is_guardian_of(tutora, ajena) is True
        assert MinorAthleteService.is_guardian_of(otra_tutora, hija) is True

    def test_no_se_puede_quitar_el_ultimo_tutor_de_un_menor(self):
        """Un menor sin tutor queda bloqueado: el último vínculo no se suelta."""
        menor = self._menor("hija_ultima")
        madre = self._tutor("madre_ultima")
        MinorAthleteService.assign_guardian(
            athlete=menor, guardian=madre, assigned_by=self.admin,
        )
        with pytest.raises(ValidationError):
            MinorAthleteService.remove_guardian(
                athlete=menor, guardian=madre, removed_by=self.admin,
            )
        assert MinorAthleteService.is_guardian_of(madre, menor) is True

    def test_el_ultimo_tutor_de_un_mayor_si_se_puede_quitar(self):
        mayor = UserFactory(
            username="ya_mayor", birth_date=datetime.date(2000, 1, 1),
        )
        AthleteProfile.objects.create(user=mayor, emergency_contact="Familia")
        tutor = self._tutor("tutor_mayor")
        Guardianship.objects.create(athlete=mayor, guardian=tutor)

        MinorAthleteService.remove_guardian(
            athlete=mayor, guardian=tutor, removed_by=self.admin,
        )
        assert MinorAthleteService.is_guardian_of(tutor, mayor) is False

    def test_quitar_un_vinculo_que_no_existe_es_idempotente(self):
        menor = self._menor("hija_idem_baja")
        madre = self._tutor("madre_idem_baja")
        ajeno = self._tutor("ajeno_idem_baja")
        MinorAthleteService.assign_guardian(
            athlete=menor, guardian=madre, assigned_by=self.admin,
        )
        MinorAthleteService.remove_guardian(
            athlete=menor, guardian=ajeno, removed_by=self.admin,
        )
        assert MinorAthleteService.is_guardian_of(madre, menor) is True

    # ── las validaciones de alta se conservan enteras ───────────────
    def test_un_headcoach_ajeno_no_puede_asignar(self):
        headcoach_role, _ = Role.objects.get_or_create(name="HEADCOACH")
        coach = UserFactory(
            username="coach_ajeno", birth_date=datetime.date(1988, 2, 2),
        )
        coach.roles.add(headcoach_role)
        menor = self._menor("hija_permiso")
        madre = self._tutor("madre_permiso")

        with pytest.raises(PermissionDenied):
            MinorAthleteService.assign_guardian(
                athlete=menor, guardian=madre, assigned_by=coach,
            )

    def test_un_headcoach_dueno_si_puede_asignar_y_queda_su_firma(self):
        headcoach_role, _ = Role.objects.get_or_create(name="HEADCOACH")
        coach = UserFactory(
            username="coach_dueno", birth_date=datetime.date(1988, 2, 2),
        )
        coach.roles.add(headcoach_role)
        menor = self._menor("hija_dueno")
        madre = self._tutor("madre_dueno")
        UserOwnership.objects.create(owner=coach, user=menor, is_active=True)

        vinculo = MinorAthleteService.assign_guardian(
            athlete=menor, guardian=madre, assigned_by=coach,
        )
        assert vinculo.created_by == coach

    def test_un_tutor_sin_fecha_de_nacimiento_se_rechaza(self):
        menor = self._menor("hija_sin_fecha")
        sin_fecha = UserFactory(username="sin_fecha", birth_date=None)
        sin_fecha.roles.add(self.guardian_role)
        with pytest.raises(ValidationError):
            MinorAthleteService.assign_guardian(
                athlete=menor, guardian=sin_fecha, assigned_by=self.admin,
            )

    def test_un_usuario_sin_rol_guardian_se_rechaza(self):
        menor = self._menor("hija_sin_rol")
        sin_rol = UserFactory(
            username="sin_rol", birth_date=datetime.date(1984, 5, 2),
        )
        with pytest.raises(ValidationError):
            MinorAthleteService.assign_guardian(
                athlete=menor, guardian=sin_rol, assigned_by=self.admin,
            )

    def test_un_atleta_mayor_no_recibe_tutores(self):
        mayor = UserFactory(
            username="mayor_sin_tutor", birth_date=datetime.date(2000, 1, 1),
        )
        AthleteProfile.objects.create(user=mayor, emergency_contact="Familia")
        tutor = self._tutor("tutor_de_mayor")
        with pytest.raises(ValidationError):
            MinorAthleteService.assign_guardian(
                athlete=mayor, guardian=tutor, assigned_by=self.admin,
            )
