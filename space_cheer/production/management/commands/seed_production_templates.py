from django.core.management.base import BaseCommand
from django.db import transaction


TEMPLATES = [
    {
        "name": "Producción estándar",
        "description": (
            "Plantilla por defecto para productos capturados al vuelo en "
            "pedidos offline: recorre todas las etapas del reglamento de "
            "producción, de selección de tallas a envíos."
        ),
        "stage_slugs": [
            "seleccion-tallas",
            "planeacion-materiales",
            "control-surtido-materiales",
            "corte",
            "sublimacion",
            "costura",
            "calidad-costura",
            "cristaleria-plantillas",
            "calidad-aplicaciones",
            "calidad-final",
            "empaque",
            "envios",
        ],
    },
]


class Command(BaseCommand):
    help = (
        "Crea las plantillas de producción por defecto (idempotente), para "
        "que el selector de plantilla de la captura offline nunca esté vacío."
    )

    def add_arguments(self, parser):
        parser.add_argument("--verbose", action="store_true")

    def handle(self, *args, **options):
        from production.models import ProductionStage, ProductionTemplate, ProductionTemplateStage

        verbose = options["verbose"]
        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for data in TEMPLATES:
                template, created = ProductionTemplate.objects.get_or_create(
                    name=data["name"],
                    defaults={"description": data["description"]},
                )
                if created:
                    created_count += 1
                    if verbose:
                        self.stdout.write(f"  [+] {template.name}")
                elif template.description != data["description"]:
                    template.description = data["description"]
                    template.save(update_fields=["description"])
                    updated_count += 1
                    if verbose:
                        self.stdout.write(f"  [~] {template.name} (actualizado)")

                for display_order, slug in enumerate(data["stage_slugs"], start=1):
                    stage = ProductionStage.objects.get(slug=slug)
                    ProductionTemplateStage.objects.update_or_create(
                        template=template,
                        stage=stage,
                        defaults={"display_order": display_order},
                    )

                # Quita del template etapas que ya no estén en la definición.
                ProductionTemplateStage.objects.filter(template=template).exclude(
                    stage__slug__in=data["stage_slugs"]
                ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_production_templates: {created_count} creadas, "
                f"{updated_count} actualizadas, "
                f"{len(TEMPLATES) - created_count - updated_count} sin cambios."
            )
        )
