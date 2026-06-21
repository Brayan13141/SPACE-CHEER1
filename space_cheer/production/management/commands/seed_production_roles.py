from django.core.management.base import BaseCommand
from django.db import transaction


# Roles based on Space Cheer's official process organization.
# Each role maps to the stages where that person is the PRIMARY responsible,
# plus the errors they are accountable for (from the Responsabilidades infographic).
ROLES = [
    {
        "name": "CONE",
        "stages": [
            "seleccion-tallas",
            "sublimacion",
            "calidad-final",
            "empaque",
        ],
        "error_responsibilities": (
            "Tallas incorrectas.\n"
            "Errores de sublimación.\n"
            "Errores que lleguen a calidad final.\n"
            "Pedidos incompletos en empaque."
        ),
    },
    {
        "name": "SR. TINO",
        "stages": [
            "planeacion-materiales",
            "corte",
        ],
        "error_responsibilities": (
            "Planeación incorrecta de materiales.\n"
            "Cortes equivocados.\n"
            "Piezas faltantes.\n"
            "Retrasos por mala programación de corte."
        ),
    },
    {
        "name": "DANI",
        "stages": [
            "control-surtido-materiales",
            "calidad-aplicaciones",
        ],
        "error_responsibilities": (
            "Materiales faltantes.\n"
            "Materiales entregados incorrectamente.\n"
            "Calidad de colocación de cristalería.\n"
            "Errores de aplicación que no respeten el proyecto."
        ),
    },
    {
        "name": "CHINO",
        "stages": [
            "cristaleria-plantillas",
        ],
        "error_responsibilities": (
            "Plantillas incompletas.\n"
            "Cristales incorrectos.\n"
            "Cantidades incorrectas de cristalería.\n"
            "Errores en preparación de aplicaciones."
        ),
    },
    {
        "name": "SRA. CHIVIS",
        "stages": [
            "costura",
        ],
        "error_responsibilities": (
            "Costuras defectuosas.\n"
            "Armado incorrecto.\n"
            "Retrabajos por confección."
        ),
    },
    {
        "name": "TERE",
        "stages": [
            "calidad-costura",
        ],
        "error_responsibilities": (
            "Errores de costura que no detectó.\n"
            "Liberación de prendas defectuosas en costura."
        ),
    },
    {
        "name": "MANUEL",
        "stages": [
            "envios",
        ],
        "error_responsibilities": (
            "Coordinación y envío del pedido fuera de fecha.\n"
            "Pedidos enviados con información incorrecta."
        ),
    },
]


class Command(BaseCommand):
    help = "Crea los roles base de producción Space Cheer (idempotente)"

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
                    defaults={
                        "created_by": None,
                        "error_responsibilities": data["error_responsibilities"],
                    },
                )
                stages = ProductionStage.objects.filter(slug__in=data["stages"])
                role.stages.set(stages)

                # Always keep error_responsibilities in sync
                if role.error_responsibilities != data["error_responsibilities"]:
                    role.error_responsibilities = data["error_responsibilities"]
                    role.save(update_fields=["error_responsibilities"])

                if created:
                    created_count += 1
                    if verbose:
                        self.stdout.write(
                            f"  [+] {role.name} "
                            f"({', '.join(s.name for s in stages)})"
                        )
                elif verbose:
                    self.stdout.write(f"  [=] {role.name} (sincronizado)")

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_production_roles: {created_count} roles creados, "
                f"{len(ROLES) - created_count} ya existían."
            )
        )
