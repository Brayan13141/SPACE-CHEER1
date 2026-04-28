import pytest
from datetime import date
from accounts.models import AthleteProfile
from custody.services.minor_access_service import MinorAccessService
from orders.tests.factories import AthleteFactory, UserFactory, UserTeamMembershipFactory


@pytest.mark.django_db
class TestMinorAccessService:

    def _make_minor(self):
        """Atleta de 15 años con AthleteProfile (sin guardian)."""
        minor = AthleteFactory(
            birth_date=date(date.today().year - 15, 1, 1),
            profile_completed=True,
        )
        AthleteProfile.objects.get_or_create(
            user=minor,
            defaults={"emergency_contact": "Contacto test"},
        )
        return minor

    def test_adulto_devuelve_none(self):
        adult = AthleteFactory(
            birth_date=date(date.today().year - 20, 1, 1),
            profile_completed=True,
        )
        assert MinorAccessService.get_access_level(adult) is None

    def test_menor_sin_guardian_es_blocked(self):
        minor = self._make_minor()
        assert MinorAccessService.get_access_level(minor) == MinorAccessService.BLOCKED

    def test_menor_con_guardian_sin_equipo_es_read_only(self):
        minor = self._make_minor()
        guardian = UserFactory()
        profile = AthleteProfile.objects.get(user=minor)
        profile.guardian = guardian
        profile.save()
        assert MinorAccessService.get_access_level(minor) == MinorAccessService.READ_ONLY

    def test_menor_con_guardian_y_equipo_activo_es_active(self):
        minor = self._make_minor()
        guardian = UserFactory()
        profile = AthleteProfile.objects.get(user=minor)
        profile.guardian = guardian
        profile.save()
        UserTeamMembershipFactory(user=minor, is_active=True, status="accepted")
        assert MinorAccessService.get_access_level(minor) == MinorAccessService.ACTIVE

    def test_menor_sin_athlete_profile_es_blocked(self):
        """Sin AthleteProfile → BLOCKED (no hay forma de verificar guardian)."""
        minor = AthleteFactory(
            birth_date=date(date.today().year - 15, 1, 1),
            profile_completed=True,
        )
        AthleteProfile.objects.filter(user=minor).delete()
        assert MinorAccessService.get_access_level(minor) == MinorAccessService.BLOCKED
