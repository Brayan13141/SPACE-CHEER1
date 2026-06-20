from django.core.management.base import BaseCommand
from django.db import transaction


STAGES = [
    {
        "display_order": 1,
        "slug": "seleccion-tallas",
        "name": "Selección de Tallas",
        "icon": "📏",
        "description": "Selección y validación de tallas según medidas y especificaciones del proyecto.",
    },
    {
        "display_order": 2,
        "slug": "planeacion-materiales",
        "name": "Planeación de Materiales",
        "icon": "📋",
        "description": "Planeación de materiales necesarios para cada proyecto y programación de producción.",
    },
    {
        "display_order": 3,
        "slug": "control-surtido-materiales",
        "name": "Control y Surtido de Materiales",
        "icon": "📦",
        "description": "Encargado de surtir y controlar que todos los materiales estén disponibles a tiempo.",
    },
    {
        "display_order": 4,
        "slug": "corte",
        "name": "Corte",
        "icon": "✂️",
        "description": "Corte de las piezas de acuerdo con el proyecto y tallas autorizadas.",
    },
    {
        "display_order": 5,
        "slug": "sublimacion",
        "name": "Sublimación",
        "icon": "🖨️",
        "description": "Sublimación de diseños y personalización de las piezas según el proyecto.",
    },
    {
        "display_order": 6,
        "slug": "costura",
        "name": "Costura",
        "icon": "🧵",
        "description": "Confección y armado de las prendas.",
    },
    {
        "display_order": 7,
        "slug": "calidad-costura",
        "name": "Calidad de Costura",
        "icon": "🔍",
        "description": "Revisión de costuras, acabados y confección antes del siguiente proceso.",
    },
    {
        "display_order": 8,
        "slug": "cristaleria-plantillas",
        "name": "Cristalería y Plantillas",
        "icon": "💎",
        "description": "Preparación de plantillas y selección de cristales según diseño del proyecto.",
    },
    {
        "display_order": 9,
        "slug": "calidad-aplicaciones",
        "name": "Calidad de Aplicaciones y Cristalería",
        "icon": "🔎",
        "description": "Revisión de colocación, medidas, colores y calidad de cristales y aplicaciones.",
    },
    {
        "display_order": 10,
        "slug": "calidad-final",
        "name": "Calidad Final",
        "icon": "✅",
        "description": "Revisión final de la prenda completa antes de empacar.",
    },
    {
        "display_order": 11,
        "slug": "empaque",
        "name": "Empaque",
        "icon": "🗃️",
        "description": "Empaque del pedido completo con todos los accesorios y etiquetado correcto.",
    },
    {
        "display_order": 12,
        "slug": "envios",
        "name": "Envíos",
        "icon": "🚚",
        "description": "Coordinación y envío del pedido al cliente en la fecha acordada.",
    },
]


class Command(BaseCommand):
    help = "Crea el catálogo base de etapas de producción Space Cheer (idempotente)"

    def add_arguments(self, parser):
        parser.add_argument("--verbose", action="store_true")

    def handle(self, *args, **options):
        from production.models import ProductionStage

        verbose = options["verbose"]
        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for data in STAGES:
                stage, created = ProductionStage.objects.get_or_create(
                    slug=data["slug"],
                    defaults={
                        "name": data["name"],
                        "icon": data["icon"],
                        "display_order": data["display_order"],
                        "description": data["description"],
                    },
                )
                if created:
                    created_count += 1
                    if verbose:
                        self.stdout.write(f"  [+] {stage.icon} {stage.name}")
                else:
                    # Update display_order and description if changed
                    changed = False
                    if stage.display_order != data["display_order"]:
                        stage.display_order = data["display_order"]
                        changed = True
                    if stage.description != data["description"]:
                        stage.description = data["description"]
                        changed = True
                    if changed:
                        stage.save(update_fields=["display_order", "description"])
                        updated_count += 1
                        if verbose:
                            self.stdout.write(f"  [~] {stage.icon} {stage.name} (actualizado)")

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_production_stages: {created_count} creadas, "
                f"{updated_count} actualizadas, "
                f"{len(STAGES) - created_count - updated_count} sin cambios."
            )
        )
