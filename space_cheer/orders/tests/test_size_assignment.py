import pytest
from django.core.exceptions import ValidationError

from measures.models import AthleteStandardSize
from orders.tests.factories import AthleteFactory
from orders.models import OrderItemAthlete
from orders.tests.factories import (
    OrderItemFactory,
    ProductWithSizesFactory,
    TeamOrderFactory,
    TeamProductWithSizesFactory,
    UserTeamMembershipFactory,
)


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


@pytest.mark.django_db
class TestOrderItemAthleteConTallaEstandar:

    def test_acepta_atleta_en_producto_team_custom_con_talla(self):
        order = TeamOrderFactory()
        product = TeamProductWithSizesFactory()
        athlete = AthleteFactory()
        UserTeamMembershipFactory(user=athlete, team=order.owner_team)
        item = OrderItemFactory(
            order=order,
            product=product,
            size_variant=product.size_variants.get(size="M"),
        )

        athlete_item = OrderItemAthlete(order_item=item, athlete=athlete)
        athlete_item.full_clean()   # no debe levantar

        athlete_item.save()
        assert item.athletes.count() == 1

    def test_sigue_rechazando_productos_globales(self):
        """Fija el alcance de la Decision 4: un producto de catalogo global no
        entra a Pieza A. Si alguien relaja clean() de mas, este test lo pesca."""
        order = TeamOrderFactory()
        product = ProductWithSizesFactory()   # usage_type = GLOBAL
        athlete = AthleteFactory()
        UserTeamMembershipFactory(user=athlete, team=order.owner_team)
        item = OrderItemFactory(
            order=order,
            product=product,
            size_variant=product.size_variants.first(),
        )

        with pytest.raises(ValidationError):
            OrderItemAthlete(order_item=item, athlete=athlete).full_clean()
