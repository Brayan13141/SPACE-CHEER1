import pytest
from datetime import date
from accounts.models import AthleteProfile, UserAddress
from custody.models import Guardianship
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
        Guardianship.objects.create(athlete=minor, guardian=guardian)
        assert MinorAccessService.get_access_level(minor) == MinorAccessService.READ_ONLY

    def test_menor_con_guardian_y_equipo_activo_es_active(self):
        minor = self._make_minor()
        guardian = UserFactory()
        Guardianship.objects.create(athlete=minor, guardian=guardian)
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


from django.test import Client


@pytest.mark.django_db
class TestMinorCannotCreateOrder:

    def test_minor_gets_redirected_on_create_order(self):
        from orders.tests.factories import RoleFactory
        athlete_role = RoleFactory(name="ATHLETE")
        minor = UserFactory(
            birth_date=date(date.today().year - 15, 1, 1),
            profile_completed=True,
            is_active=True,
        )
        minor.roles.add(athlete_role)
        minor.set_password("testpass1234!")
        minor.save()

        client = Client()
        client.login(username=minor.username, password="testpass1234!")

        response = client.post("/orders/create/", {"order_type": "PERSONAL"})

        # El menor debe ser redirigido, no se crea ninguna orden
        assert response.status_code == 302
        from orders.models import Order
        assert not Order.objects.filter(created_by=minor).exists()


from orders.models import Order


@pytest.mark.django_db
class TestGuardianCreateOrder:

    def _setup(self):
        from orders.tests.factories import RoleFactory
        guardian_role = RoleFactory(name="GUARDIAN")
        guardian = UserFactory(profile_completed=True, is_active=True)
        guardian.roles.add(guardian_role)
        guardian.set_password("testpass1234!")
        guardian.save()

        minor = AthleteFactory(
            birth_date=date(date.today().year - 15, 1, 1),
            profile_completed=True,
        )
        AthleteProfile.objects.get_or_create(
            user=minor,
            defaults={"emergency_contact": "Contacto test"},
        )
        Guardianship.objects.create(athlete=minor, guardian=guardian)

        UserAddress.objects.create(
            user=minor,
            label="Casa",
            address="Calle Falsa 123",
            city="Ciudad de México",
            zip_code="06600",
            is_default=True,
        )

        return guardian, minor

    def test_guardian_puede_crear_orden_para_su_menor(self):
        guardian, minor = self._setup()
        client = Client()
        client.login(username=guardian.username, password="testpass1234!")

        response = client.post(f"/guardian/order/create/{minor.id}/")

        assert response.status_code == 302
        assert Order.objects.filter(owner_user=minor, created_by=guardian).exists()

    def test_guardian_no_puede_crear_orden_para_atleta_ajeno(self):
        guardian, minor = self._setup()
        otro_menor = AthleteFactory(
            birth_date=date(date.today().year - 15, 1, 1),
            profile_completed=True,
        )
        AthleteProfile.objects.get_or_create(
            user=otro_menor,
            defaults={"emergency_contact": "Otro contacto"},
        )

        client = Client()
        client.login(username=guardian.username, password="testpass1234!")

        response = client.post(f"/guardian/order/create/{otro_menor.id}/")

        assert response.status_code == 302
        assert not Order.objects.filter(owner_user=otro_menor, created_by=guardian).exists()
