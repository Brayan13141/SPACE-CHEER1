from django.core.management.base import BaseCommand
from django.db import transaction


ROLES = [
    {
        "name": "Diseñador",
        "stages": ["diseno", "logos"],
    },
    {
        "name": "Cristalero",
        "stages": ["cristaleria", "pega_cristaleria"],
    },
    {
        "name": "Cortador/Costurero",
        "stages": ["moldaje", "corte", "semiarmado", "armado_final"],
    },
    {
        "name": "Logística",
        "stages": ["envio"],
    },
]


class Command(BaseCommand):
    help = "Crea los roles base de producción (idempotente)"

    def add_arguments(self, parser):
        parser.add_argument("--verbose", action="store_true")

    def handle(self, *args, **options):
        from production.models import ProductionRole, ProductionStage

        verbose = options["verbose"]
        created_count = 0

        with transaction.atomic():
            for data in ROLES:
                role, created = ProductionRole.objects.get_or_create(
                    name=data["name"],
                    defaults={"created_by": None},
                )
                stages = ProductionStage.objects.filter(slug__in=data["stages"])
                role.stages.set(stages)

                if created:
                    created_count += 1
                    if verbose:
                        self.stdout.write(
                            f"  Rol creado: {role.name} "
                            f"({', '.join(s.name for s in stages)})"
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_production_roles: {created_count} roles creados, "
                f"{len(ROLES) - created_count} ya existían."
            )
        )
