import factory
from factory.django import DjangoModelFactory
from factory import fuzzy
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from accounts.models import User, Role
from teams.models import Team, TeamCategory, UserTeamMembership
from products.models import Product, Season, ProductSizeVariant, ProductMeasurementField
from measures.models import MeasurementField
from orders.models import (
    Order,
    OrderItem,
    OrderItemAthlete,
    OrderItemMeasurement,
    OrderContactInfo,
    OrderDesignImage,
    OrderLog,
)


# ============================================================
# ACCOUNTS & TEAMS
# ============================================================


class RoleFactory(DjangoModelFactory):
    class Meta:
        model = Role
        django_get_or_create = ("name",)

    name = factory.Iterator(["ADMIN", "HEADCOACH", "COACH", "ATHLETE", "STAFF"])
    requires_curp = False
    is_staff_type = False
    is_athlete_type = factory.LazyAttribute(lambda o: o.name == "ATHLETE")
    is_coach_type = factory.LazyAttribute(lambda o: o.name in ["HEADCOACH", "COACH"])


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@test.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    phone = factory.Sequence(lambda n: f"55{n:08d}")
    is_active = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "testpassword123")

        user = model_class(*args, **kwargs)
        user.set_password(password)  # ✔️ antes de save
        user.full_clean()  # ✔️ valida ya con password
        user.save()

        return user

    @factory.post_generation
    def roles(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for role in extracted:
                self.roles.add(role)


class CoachFactory(UserFactory):
    @factory.post_generation
    def roles(self, create, extracted, **kwargs):
        if create:
            role = RoleFactory(name="HEADCOACH")
            self.roles.add(role)


class AthleteFactory(UserFactory):
    @factory.post_generation
    def roles(self, create, extracted, **kwargs):
        if create:
            role = RoleFactory(name="ATHLETE")
            self.roles.add(role)


class TeamCategoryFactory(DjangoModelFactory):
    class Meta:
        model = TeamCategory

    name = factory.Sequence(lambda n: f"Categoría {n}")
    level = factory.Sequence(lambda n: n)


class TeamFactory(DjangoModelFactory):
    class Meta:
        model = Team

    name = factory.Sequence(lambda n: f"Team {n}")
    coach = factory.SubFactory(CoachFactory)
    city = factory.Faker("city")
    phone = factory.Sequence(lambda n: f"55{n:08d}")
    category = factory.SubFactory(TeamCategoryFactory)


class UserTeamMembershipFactory(DjangoModelFactory):
    class Meta:
        model = UserTeamMembership

    user = factory.SubFactory(AthleteFactory)
    team = factory.SubFactory(TeamFactory)
    role_in_team = "ATHLETE"
    status = "accepted"
    is_active = True


# ============================================================
# PRODUCTS
# ============================================================


class SeasonFactory(DjangoModelFactory):
    class Meta:
        model = Season

    name = factory.Sequence(lambda n: f"Season {n}")
    is_active = True


class MeasurementFieldFactory(DjangoModelFactory):
    class Meta:
        model = MeasurementField

    name = factory.Sequence(lambda n: f"Campo {n}")
    slug = factory.Sequence(lambda n: f"campo_{n}")  # 🔥 evita colisiones
    field_type = "decimal"
    unit = "cm"
    required = True
    order = factory.Sequence(lambda n: n)


class ProductFactory(DjangoModelFactory):
    """
     Factory BASE segura:
    - Nunca crea estados inválidos
    - Auto-corrige inconsistencias
    """

    class Meta:
        model = Product
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"Product {n}")
    description = factory.Faker("text", max_nb_chars=200)
    product_type = "UNIFORM"
    usage_type = "GLOBAL"
    scope = "CATALOG"
    size_strategy = "NONE"
    season = factory.SubFactory(SeasonFactory)
    base_price = Decimal("100.00")
    is_active = True
    is_configured = True
    size_strategy = factory.LazyAttribute(
        lambda o: "MEASUREMENTS" if o.usage_type == "TEAM_CUSTOM" else "NONE"
    )

    @factory.post_generation
    def ensure_domain_consistency(self, create, extracted, **kwargs):
        """
        Garantiza que el producto siempre sea válido según reglas de dominio
        """
        if not create:
            return

        changed = False

        # ❗ Regla: TEAM_CUSTOM no puede ser NONE
        if self.usage_type == "TEAM_CUSTOM" and self.size_strategy == "NONE":
            self.size_strategy = "MEASUREMENTS"
            changed = True

        # ❗ Regla: MEASUREMENTS requiere fields
        if self.size_strategy == "MEASUREMENTS":
            if not self.measurement_fields.exists():
                field1 = MeasurementFieldFactory(name="Pecho")
                field2 = MeasurementFieldFactory(name="Cintura")

                ProductMeasurementFieldFactory(product=self, field=field1)
                ProductMeasurementFieldFactory(product=self, field=field2)

        # ❗ Regla: STANDARD requiere size variants
        if self.size_strategy == "STANDARD":
            if not self.size_variants.exists():
                for size in ["CH", "M", "G", "XG"]:
                    ProductSizeVariantFactory(product=self, size=size)

        if changed:
            self.save()


class ProductWithSizesFactory(ProductFactory):
    class Meta:
        model = Product
        skip_postgeneration_save = True

    usage_type = "GLOBAL"
    size_strategy = "STANDARD"

    @factory.post_generation
    def sizes(self, create, extracted, **kwargs):
        if not create:
            return

        if not self.size_variants.exists():
            for size in ["CH", "M", "G", "XG"]:
                ProductSizeVariantFactory(product=self, size=size)


class ProductWithMeasurementsFactory(ProductFactory):
    class Meta:
        model = Product
        skip_postgeneration_save = True

    usage_type = "TEAM_CUSTOM"
    size_strategy = "MEASUREMENTS"

    @factory.post_generation
    def measurement_fields(self, create, extracted, **kwargs):
        if not create:
            return

        field1 = MeasurementFieldFactory(name="Pecho")
        field2 = MeasurementFieldFactory(name="Cintura")

        ProductMeasurementFieldFactory(product=self, field=field1)
        ProductMeasurementFieldFactory(product=self, field=field2)


class ProductSizeVariantFactory(DjangoModelFactory):
    class Meta:
        model = ProductSizeVariant

    product = factory.SubFactory(ProductFactory)
    size = "M"
    additional_price = Decimal("0.00")


class ProductMeasurementFieldFactory(DjangoModelFactory):
    class Meta:
        model = ProductMeasurementField

    product = factory.SubFactory(ProductFactory)
    field = factory.SubFactory(MeasurementFieldFactory)
    required = True


# ============================================================
# ORDERS
# ============================================================


class OrderFactory(DjangoModelFactory):
    class Meta:
        model = Order

    order_type = "PERSONAL"
    status = "DRAFT"
    created_by = factory.SubFactory(UserFactory)
    owner_user = factory.LazyAttribute(
        lambda o: o.created_by if o.order_type == "PERSONAL" else None
    )
    owner_team = factory.LazyAttribute(
        lambda o: TeamFactory() if o.order_type == "TEAM" else None
    )
    measurements_open = True
    measurements_locked = False


class TeamOrderFactory(OrderFactory):
    order_type = "TEAM"
    owner_user = None
    owner_team = factory.SubFactory(TeamFactory)
    created_by = factory.LazyAttribute(lambda o: o.owner_team.coach)


class OrderContactInfoFactory(DjangoModelFactory):
    class Meta:
        model = OrderContactInfo

    order = factory.SubFactory(OrderFactory)
    contact_name = factory.Faker("name")
    contact_phone = factory.Sequence(lambda n: f"55{n:08d}")
    contact_email = factory.Faker("email")
    shipping_address_line = factory.Faker("street_address")
    shipping_city = factory.Faker("city")
    shipping_postal_code = factory.Faker("postcode")
    closed = True


class OrderItemFactory(DjangoModelFactory):
    class Meta:
        model = OrderItem
        skip_postgeneration_save = True

    order = factory.SubFactory("orders.tests.factories.OrderFactory")
    product = factory.SubFactory(ProductFactory)
    quantity = 1

    # ❗ NO definas unit_price directamente
    # deja que el modelo lo calcule

    @factory.post_generation
    def force_unit_price(self, create, extracted, **kwargs):
        """
        🔥 Permite forzar unit_price SOLO si el test lo necesita
        Uso:
        OrderItemFactory(force_unit_price=Decimal("50.00"))
        """
        if not create:
            return

        if extracted is not None:
            # ⚠️ bypass lógica del modelo si es necesario
            OrderItem.objects.filter(pk=self.pk).update(unit_price=extracted)
            self.refresh_from_db()


class OrderItemAthleteFactory(DjangoModelFactory):
    class Meta:
        model = OrderItemAthlete

    order_item = factory.SubFactory(OrderItemFactory)
    athlete = factory.SubFactory(AthleteFactory)


class OrderItemMeasurementFactory(DjangoModelFactory):
    class Meta:
        model = OrderItemMeasurement

    athlete_item = factory.SubFactory(OrderItemAthleteFactory)
    field = factory.SubFactory(MeasurementFieldFactory)
    field_name = factory.LazyAttribute(lambda o: o.field.name)
    field_unit = factory.LazyAttribute(lambda o: o.field.unit)
    value = "100"


class OrderDesignImageFactory(DjangoModelFactory):
    class Meta:
        model = OrderDesignImage

    order = factory.SubFactory(OrderFactory)
    image = factory.django.ImageField(color="blue")
    uploaded_by = factory.SubFactory(UserFactory)
    is_final = False


class OrderLogFactory(DjangoModelFactory):
    class Meta:
        model = OrderLog

    order = factory.SubFactory(OrderFactory)
    user = factory.SubFactory(UserFactory)
    action = "STATUS_CHANGE"
    from_status = "DRAFT"
    to_status = "PENDING"
