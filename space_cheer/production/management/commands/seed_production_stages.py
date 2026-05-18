from django.core.management.base import BaseCommand
from django.db import transaction


STAGES = [
    {"display_order": 1, "slug": "diseno",           "name": "Diseño",               "icon": "🎨"},
    {"display_order": 2, "slug": "moldaje",          "name": "Moldaje",              "icon": "📐"},
    {"display_order": 3, "slug": "cristaleria",      "name": "Cristalería",          "icon": "💎"},
    {"display_order": 4, "slug": "logos",            "name": "Logos",                "icon": "🖊"},
    {"display_order": 5, "slug": "corte",            "name": "Corte",                "icon": "✂️"},
    {"display_order": 6, "slug": "semiarmado",       "name": "Semiarmado",           "icon": "🧵"},
    {"display_order": 7, "slug": "pega_cristaleria", "name": "Pega de cristalería",  "icon": "✨"},
    {"display_order": 8, "slug": "armado_final",     "name": "Armado final",         "icon": "🔒"},
    {"display_order": 9, "slug": "envio",            "name": "Envío",                "icon": "📦"},
]


class Command(BaseCommand):
    help = "Crea el catálogo base de etapas de producción (idempotente)"

    def add_arguments(self, parser):
        parser.add_argument("--verbose", action="store_true")

    def handle(self, *args, **options):
        from production.models import ProductionStage

        verbose = options["verbose"]
        created_count = 0

        with transaction.atomic():
            for data in STAGES:
                stage, created = ProductionStage.objects.get_or_create(
                    slug=data["slug"],
                    defaults={
                        "name": data["name"],
                        "icon": data["icon"],
                        "display_order": data["display_order"],
                    },
                )
                if created:
                    created_count += 1
                    if verbose:
                        self.stdout.write(f"  Etapa creada: {stage.icon} {stage.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_production_stages: {created_count} etapas creadas, "
                f"{len(STAGES) - created_count} ya existían."
            )
        )
