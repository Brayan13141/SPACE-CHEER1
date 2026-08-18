from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from measures.models import AthleteStandardSize
from orders.tests.factories import AthleteFactory
from orders.models import OrderItem, OrderItemAthlete
from orders.services.servicesItems.size_assignment_service import (
    OrderItemSizeAssignmentService,
)
from orders.tests.factories import (
    AthleteStandardSizeFactory,
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


def setup_team_roster(sizes=None):
    """Helper A NIVEL DE MODULO. Las demas clases de test de este archivo lo
    llaman directamente: instanciar una clase de test desde otra
    (TestX()._setup()) funciona por accidente en pytest y es lo que un reviewer
    marca."""
    order = TeamOrderFactory()
    product = TeamProductWithSizesFactory(sizes=sizes)
    athletes = [AthleteFactory() for _ in range(3)]
    for athlete in athletes:
        UserTeamMembershipFactory(user=athlete, team=order.owner_team)
    return order, product, athletes


@pytest.mark.django_db
class TestConciliacion:

    def _setup(self, sizes=None):
        return setup_team_roster(sizes=sizes)

    def test_crea_un_item_por_talla_con_su_cantidad(self):
        order, product, (a1, a2, a3) = self._setup()

        result = OrderItemSizeAssignmentService.reconcile(
            order, product,
            {a1.id: "M", a2.id: "M", a3.id: "L"},
            viewer=order.created_by,
        )

        assert result.ok
        items = {i.size_variant.size: i for i in order.items.all()}
        assert set(items) == {"M", "L"}
        assert items["M"].quantity == 2
        assert items["L"].quantity == 1
        assert set(items["M"].athletes.values_list("athlete_id", flat=True)) == {a1.id, a2.id}

    def test_mover_de_talla_reubica_al_alumno_y_ajusta_cantidades(self):
        order, product, (a1, a2, a3) = self._setup()
        OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "M", a2.id: "M"}, viewer=order.created_by
        )

        OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "L", a2.id: "M"}, viewer=order.created_by
        )

        items = {i.size_variant.size: i for i in order.items.all()}
        assert items["M"].quantity == 1
        assert items["L"].quantity == 1
        assert items["L"].athletes.get().athlete_id == a1.id

    def test_el_item_que_se_queda_sin_alumnos_se_elimina(self):
        order, product, (a1, a2, a3) = self._setup()
        OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "M"}, viewer=order.created_by
        )

        OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "L"}, viewer=order.created_by
        )

        assert not order.items.filter(size_variant__size="M").exists()

    def test_captura_parcial_talla_vacia_no_bloquea_a_los_demas(self):
        order, product, (a1, a2, a3) = self._setup()

        result = OrderItemSizeAssignmentService.reconcile(
            order, product,
            {a1.id: "M", a2.id: "", a3.id: "L"},
            viewer=order.created_by,
        )

        assert result.ok
        assert order.items.count() == 2
        assert not order.items.filter(athletes__athlete_id=a2.id).exists()

    def test_talla_que_el_producto_no_ofrece_falla_solo_esa_fila(self):
        order, product, (a1, a2, a3) = self._setup(sizes=["S", "M", "L"])

        result = OrderItemSizeAssignmentService.reconcile(
            order, product,
            {a1.id: "M", a2.id: "XXL", a3.id: "L"},
            viewer=order.created_by,
        )

        assert not result.ok
        assert a2.id in result.errors
        assert "XXL" in result.errors[a2.id]
        # Las otras dos SI se guardaron: un valor malo no tumba la captura.
        assert order.items.count() == 2

    def test_el_precio_suma_los_adicionales_de_cada_talla(self):
        order, product, (a1, a2, a3) = self._setup()
        variant = product.size_variants.get(size="XL")
        variant.additional_price = Decimal("100.00")
        variant.save()

        OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "M", a2.id: "XL"}, viewer=order.created_by
        )

        items = {i.size_variant.size: i for i in order.items.all()}
        assert items["M"].unit_price == product.base_price
        assert items["XL"].unit_price == product.base_price + Decimal("100.00")

    def test_alumno_que_ya_no_es_del_equipo_pierde_su_fila(self):
        order, product, (a1, a2, a3) = self._setup()
        OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "M", a2.id: "M"}, viewer=order.created_by
        )
        membership = a2.team_memberships.get(team=order.owner_team)
        membership.is_active = False
        membership.save()

        result = OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "M", a2.id: "M"}, viewer=order.created_by
        )

        assert a2.id in result.errors
        assert order.items.get(size_variant__size="M").quantity == 1

    def test_un_roster_parcial_no_borra_las_filas_de_los_demas(self):
        """CRITICO: reconcile() concilia estado completo, pero la vista le pasa
        SOLO las filas editables del que guarda. Para un tutor eso es una sola
        fila, asi que todo el resto del equipo quedaba 'stale' y se borraba, con
        sus items y las cantidades del pedido."""
        order, product, (a1, a2, a3) = self._setup()
        OrderItemSizeAssignmentService.reconcile(
            order, product,
            {a1.id: "M", a2.id: "M", a3.id: "L"},
            viewer=order.created_by,
        )

        # El tutor de a1 guarda unicamente la fila de su hijo.
        OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "S"}, viewer=order.created_by
        )

        items = {i.size_variant.size: i for i in order.items.all()}
        assert set(items) == {"S", "M", "L"}          # nadie perdio su talla
        assert items["M"].quantity == 1               # a2 sigue en M
        assert items["L"].quantity == 1               # a3 sigue en L
        assert set(items["S"].athletes.values_list("athlete_id", flat=True)) == {a1.id}

    def test_un_roster_parcial_limpia_al_que_ya_no_es_del_equipo(self):
        """La contracara: la fila de alguien que ya no es atleta activo se
        retira aunque no venga en el roster que se esta guardando; esa fila no
        puede ser valida para nadie."""
        order, product, (a1, a2, a3) = self._setup()
        OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "M", a2.id: "M"}, viewer=order.created_by
        )
        membership = a2.team_memberships.get(team=order.owner_team)
        membership.is_active = False
        membership.save()

        OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "M"}, viewer=order.created_by
        )

        item = order.items.get(size_variant__size="M")
        assert set(item.athletes.values_list("athlete_id", flat=True)) == {a1.id}
        assert item.quantity == 1

    def test_un_producto_fuera_del_catalogo_de_la_orden_no_se_puede_inyectar(self):
        """SEGURIDAD (IDOR de producto): la orden esta autorizada, el producto no.

        reconcile() crea OrderItem directo, saltandose el filtro de catalogo
        que si aplica OrderItemService.add_product. Un producto retirado (su
        temporada ya no esta activa) pasa OrderItem.clean() sin problema
        --clean solo frena los TEAM_ONLY de otro equipo-- asi que sin esta
        guarda un coach autorizado en su propia orden le inyecta un producto
        que la politica de catalogo no le permitia pedir.
        """
        order, product, (a1, a2, a3) = self._setup()
        product.season.is_active = False
        product.season.save()

        with pytest.raises(ValidationError):
            OrderItemSizeAssignmentService.reconcile(
                order, product, {a1.id: "M"}, viewer=order.created_by
            )

        assert not order.items.exists()

    def test_reconcile_no_duplica_items_de_la_misma_talla(self):
        """Documenta el invariante del lock a nivel de Order: llamar reconcile()
        dos veces seguidas con la misma asignacion nunca produce dos OrderItem
        para la misma talla. El caso concurrente real (dos coaches creando la
        misma talla por primera vez al mismo tiempo) no es probable con threads
        aqui; lo cierra el select_for_update sobre Order en reconcile()."""
        order, product, (a1, a2, a3) = self._setup()

        OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "M", a2.id: "M"}, viewer=order.created_by
        )
        OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "M", a2.id: "M"}, viewer=order.created_by
        )

        assert order.items.filter(size_variant__size="M").count() == 1
        assert order.items.get(size_variant__size="M").quantity == 2


@pytest.mark.django_db
class TestWriteBackAlPerfil:

    def test_guardar_el_roster_actualiza_la_talla_del_alumno(self):
        order, product, (a1, a2, a3) = setup_team_roster()

        result = OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "L"}, viewer=order.created_by
        )

        a1.refresh_from_db()
        assert a1.standard_size.size == "L"
        assert a1.standard_size.updated_by_id == order.created_by.id
        assert a1.id in result.profile_updates

    def test_no_escribe_cuando_la_talla_no_cambio(self):
        order, product, (a1, a2, a3) = setup_team_roster()
        AthleteStandardSizeFactory(user=a1, size="M")
        antes = AthleteStandardSize.objects.get(user=a1).updated_at

        result = OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "M"}, viewer=order.created_by
        )

        assert result.profile_updates == []
        assert AthleteStandardSize.objects.get(user=a1).updated_at == antes

    def test_una_talla_valida_del_producto_pero_fuera_de_la_escala_no_toca_el_perfil(self):
        """Un 42 de calzado es una talla legitima del producto y NO pertenece a
        la escala XS-XXL del alumno: nunca debe escribirse en su perfil."""
        order, product, (a1, a2, a3) = setup_team_roster(sizes=["S", "M", "42"])

        result = OrderItemSizeAssignmentService.reconcile(
            order, product, {a1.id: "42"}, viewer=order.created_by
        )

        assert result.ok
        assert result.profile_updates == []
        assert not AthleteStandardSize.objects.filter(user=a1).exists()
        # La asignacion en el pedido SI ocurre: el producto ofrece esa talla.
        assert order.items.get(size_variant__size="42").athletes.count() == 1
