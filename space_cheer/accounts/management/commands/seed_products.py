# accounts/management/commands/seed_products.py
"""
Pobla la BD con temporada, campos de medición, productos y categorías de equipo.

Uso:
    python manage.py seed_products
    python manage.py seed_products --reset

Idempotente. Seguro de correr múltiples veces.
Orden:
    1. Temporada activa
    2. Campos de medición (measures.MeasurementField)
    3. Categorías de equipo (teams.TeamCategory)
    4. Productos con variantes de talla y campos de medida
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

SEASON_NAME = "Temporada 2026"

MEASUREMENT_FIELDS_DATA = [
    {"name": "Estatura",         "slug": "estatura",       "field_type": "decimal", "unit": "cm", "required": True,  "order": 1},
    {"name": "Pecho",            "slug": "pecho",          "field_type": "decimal", "unit": "cm", "required": True,  "order": 2},
    {"name": "Cintura",          "slug": "cintura",        "field_type": "decimal", "unit": "cm", "required": True,  "order": 3},
    {"name": "Cadera",           "slug": "cadera",         "field_type": "decimal", "unit": "cm", "required": True,  "order": 4},
    {"name": "Entrepierna",      "slug": "entrepierna",    "field_type": "decimal", "unit": "cm", "required": True,  "order": 5},
    {"name": "Ancho de hombros", "slug": "ancho-hombros",  "field_type": "decimal", "unit": "cm", "required": True,  "order": 6},
    {"name": "Talla de zapato",  "slug": "talla-zapato",   "field_type": "decimal", "unit": "cm", "required": True,  "order": 7},
    {"name": "Peso",             "slug": "peso",           "field_type": "decimal", "unit": "kg", "required": False, "order": 8},
]

TEAM_CATEGORIES_DATA = [
    {"name": "Juvenil Nivel 1", "level": 1, "description": "Categoría juvenil básica, edades 10-13"},
    {"name": "Juvenil Nivel 2", "level": 2, "description": "Categoría juvenil intermedia, edades 12-15"},
    {"name": "Juvenil Nivel 3", "level": 3, "description": "Categoría juvenil avanzada, edades 14-17"},
    {"name": "Senior Nivel 1",  "level": 4, "description": "Categoría senior básica, 18+"},
    {"name": "Senior Nivel 2",  "level": 5, "description": "Categoría senior avanzada, élite"},
]

PRODUCTS_DATA = [
    {
        "name": "Uniforme Base",
        "description": "Uniforme estándar de competencia con tallas predefinidas. Incluye top y short.",
        "product_type": "UNIFORM",
        "usage_type": "GLOBAL",
        "scope": "CATALOG",
        "size_strategy": "STANDARD",
        "base_price": Decimal("1200.00"),
        "sizes": [
            ("XS",  Decimal("0.00")),
            ("S",   Decimal("0.00")),
            ("M",   Decimal("0.00")),
            ("L",   Decimal("50.00")),
            ("XL",  Decimal("100.00")),
            ("XXL", Decimal("150.00")),
        ],
        "measurement_slugs": [],
    },
    {
        "name": "Tenis de Competencia",
        "description": "Tenis oficiales de competencia en tallas numéricas en centímetros.",
        "product_type": "SHOES",
        "usage_type": "GLOBAL",
        "scope": "CATALOG",
        "size_strategy": "STANDARD",
        "base_price": Decimal("850.00"),
        "sizes": [
            ("23", Decimal("0.00")),
            ("24", Decimal("0.00")),
            ("25", Decimal("0.00")),
            ("26", Decimal("0.00")),
            ("27", Decimal("0.00")),
            ("28", Decimal("0.00")),
            ("29", Decimal("50.00")),
            ("30", Decimal("50.00")),
        ],
        "measurement_slugs": [],
    },
    {
        "name": "Mochila Space Cheer",
        "description": "Mochila oficial del equipo con logo. Sin talla.",
        "product_type": "BAG",
        "usage_type": "GLOBAL",
        "scope": "CATALOG",
        "size_strategy": "NONE",
        "base_price": Decimal("450.00"),
        "sizes": [],
        "measurement_slugs": [],
    },
    {
        "name": "Accesorio Porrista",
        "description": "Pompón oficial de competencia. Sin talla.",
        "product_type": "OTHER",
        "usage_type": "GLOBAL",
        "scope": "CATALOG",
        "size_strategy": "NONE",
        "base_price": Decimal("180.00"),
        "sizes": [],
        "measurement_slugs": [],
    },
    {
        "name": "Uniforme Personalizado por Equipo",
        "description": "Uniforme con diseño del equipo, confeccionado a medida del atleta.",
        "product_type": "UNIFORM",
        "usage_type": "TEAM_CUSTOM",
        "scope": "CATALOG",
        "size_strategy": "MEASUREMENTS",
        "base_price": Decimal("1800.00"),
        "sizes": [],
        "measurement_slugs": ["estatura", "pecho", "cintura", "cadera", "entrepierna", "ancho-hombros"],
    },
    {
        "name": "Uniforme Atleta Custom",
        "description": "Uniforme completamente personalizado con nombre, número y medidas del atleta.",
        "product_type": "UNIFORM",
        "usage_type": "ATHLETE_CUSTOM",
        "scope": "CATALOG",
        "size_strategy": "MEASUREMENTS",
        "base_price": Decimal("2500.00"),
        "sizes": [],
        "measurement_slugs": ["estatura", "pecho", "cintura", "cadera", "entrepierna", "ancho-hombros", "talla-zapato"],
    },
    {
        "name": "Shorts de Entrenamiento",
        "description": "Shorts oficiales para práctica diaria.",
        "product_type": "UNIFORM",
        "usage_type": "GLOBAL",
        "scope": "CATALOG",
        "size_strategy": "STANDARD",
        "base_price": Decimal("320.00"),
        "sizes": [
            ("XS", Decimal("0.00")),
            ("S",  Decimal("0.00")),
            ("M",  Decimal("0.00")),
            ("L",  Decimal("30.00")),
            ("XL", Decimal("60.00")),
        ],
        "measurement_slugs": [],
    },
]


class Command(BaseCommand):
    help = "Crea temporada, campos de medición, categorías de equipo y productos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Elimina los productos y la temporada del seed antes de recrearlos",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== seed_products ==="))

        with transaction.atomic():
            if options["reset"]:
                self._reset()

            season = self._seed_season()
            fields = self._seed_measurement_fields()
            self._seed_team_categories()
            self._seed_products(season, fields)

        self.stdout.write(self.style.SUCCESS("\n✔ seed_products completado."))

    # ═══════════════════════════════════════════════════════════════
    # RESET
    # ═══════════════════════════════════════════════════════════════

    def _reset(self):
        from products.models import Product, Season

        self.stdout.write(self.style.WARNING("  [RESET] Borrando datos del seed..."))
        names = [p["name"] for p in PRODUCTS_DATA]
        deleted, _ = Product.objects.filter(name__in=names).delete()
        self.stdout.write(f"    Productos eliminados: {deleted}")

        season_deleted, _ = Season.objects.filter(name=SEASON_NAME).delete()
        self.stdout.write(f"    Temporadas eliminadas: {season_deleted}")
        self.stdout.write(self.style.WARNING("  [RESET] Listo.\n"))

    # ═══════════════════════════════════════════════════════════════
    # 1. TEMPORADA
    # ═══════════════════════════════════════════════════════════════

    def _seed_season(self):
        from products.models import Season

        self.stdout.write(self.style.MIGRATE_LABEL("\n[1/4] Temporada"))
        season, created = Season.objects.get_or_create(
            name=SEASON_NAME,
            defaults={"is_active": True},
        )
        if not season.is_active:
            season.is_active = True
            season.save(update_fields=["is_active"])

        action = "CREADA" if created else "ya existe"
        self.stdout.write(f"    {season.name}: {action}")
        return season

    # ═══════════════════════════════════════════════════════════════
    # 2. CAMPOS DE MEDICIÓN
    # ═══════════════════════════════════════════════════════════════

    def _seed_measurement_fields(self):
        from measures.models import MeasurementField

        self.stdout.write(self.style.MIGRATE_LABEL("\n[2/4] Campos de medición"))
        fields = {}
        for data in MEASUREMENT_FIELDS_DATA:
            slug = data["slug"]
            field, created = MeasurementField.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": data["name"],
                    "field_type": data["field_type"],
                    "unit": data["unit"],
                    "required": data["required"],
                    "order": data["order"],
                    "is_active": True,
                },
            )
            fields[slug] = field
            action = "CREADO" if created else "ya existe"
            self.stdout.write(f"    {field.name} ({slug}): {action}")

        return fields

    # ═══════════════════════════════════════════════════════════════
    # 3. CATEGORÍAS DE EQUIPO
    # ═══════════════════════════════════════════════════════════════

    def _seed_team_categories(self):
        from teams.models import TeamCategory

        self.stdout.write(self.style.MIGRATE_LABEL("\n[3/4] Categorías de equipo"))
        for data in TEAM_CATEGORIES_DATA:
            cat, created = TeamCategory.objects.get_or_create(
                name=data["name"],
                defaults={"level": data["level"], "description": data["description"]},
            )
            action = "CREADA" if created else "ya existe"
            self.stdout.write(f"    {cat.name}: {action}")

    # ═══════════════════════════════════════════════════════════════
    # 4. PRODUCTOS
    # ═══════════════════════════════════════════════════════════════

    def _seed_products(self, season, fields):
        from products.models import Product, ProductMeasurementField, ProductSizeVariant

        self.stdout.write(self.style.MIGRATE_LABEL("\n[4/4] Productos"))

        for data in PRODUCTS_DATA:
            name = data["name"]
            existing = Product.objects.filter(name=name, season=season).first()

            if existing:
                self.stdout.write(f"    {name}: ya existe")
                product = existing
            else:
                product = Product(
                    name=name,
                    description=data["description"],
                    product_type=data["product_type"],
                    usage_type=data["usage_type"],
                    scope=data["scope"],
                    size_strategy=data["size_strategy"],
                    base_price=data["base_price"],
                    season=season,
                    is_active=True,
                )
                # save() llama full_clean() internamente
                product.save()
                self.stdout.write(self.style.SUCCESS(f"    CREADO: {name}"))

            # Variantes de talla
            for size, extra in data["sizes"]:
                ProductSizeVariant.objects.get_or_create(
                    product=product,
                    size=size,
                    defaults={"additional_price": extra},
                )

            # Campos de medida
            for slug in data["measurement_slugs"]:
                if slug in fields:
                    ProductMeasurementField.objects.get_or_create(
                        product=product,
                        field=fields[slug],
                        defaults={"required": True},
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"      Campo '{slug}' no encontrado, omitido")
                    )

            # Actualizar is_configured
            product.update_configuration_status()
            self.stdout.write(
                f"      configured={product.is_configured}  "
                f"variants={product.size_variants.count()}  "
                f"measure_fields={product.measurement_fields.count()}"
            )
