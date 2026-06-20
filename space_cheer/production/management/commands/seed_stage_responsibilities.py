from django.core.management.base import BaseCommand
from django.db import transaction


# Stage → responsible role + auxiliary roles
# Based on the "Responsables y Auxiliares" infographic.
RESPONSIBILITIES = [
    {
        "stage": "seleccion-tallas",
        "responsible": "CONE",
        "auxiliaries": ["CHINO", "DANI"],
    },
    {
        "stage": "planeacion-materiales",
        "responsible": "SR. TINO",
        "auxiliaries": ["CHINO"],
    },
    {
        "stage": "control-surtido-materiales",
        "responsible": "DANI",
        "auxiliaries": ["CHINO"],
    },
    {
        "stage": "corte",
        "responsible": "SR. TINO",
        "auxiliaries": [],
    },
    {
        "stage": "sublimacion",
        "responsible": "CONE",
        "auxiliaries": ["DANI", "CHINO"],
    },
    {
        "stage": "costura",
        "responsible": "SRA. CHIVIS",
        "auxiliaries": [],
    },
    {
        "stage": "calidad-costura",
        "responsible": "TERE",
        "auxiliaries": [],
    },
    {
        "stage": "cristaleria-plantillas",
        "responsible": "CHINO",
        "auxiliaries": ["DANI"],
    },
    {
        "stage": "calidad-aplicaciones",
        "responsible": "DANI",
        "auxiliaries": ["CHINO"],
    },
    {
        "stage": "calidad-final",
        "responsible": "CONE",
        "auxiliaries": ["DANI", "CHINO"],
    },
    {
        "stage": "empaque",
        "responsible": "CONE",
        "auxiliaries": ["DANI"],
    },
    {
        "stage": "envios",
        "responsible": "MANUEL",
        "auxiliaries": ["CHINO"],
    },
]


class Command(BaseCommand):
    help = "Asigna responsables y auxiliares a las etapas de producción (idempotente)"

    def add_arguments(self, parser):
        parser.add_argument("--verbose", action="store_true")

    def handle(self, *args, **options):
        from production.models import ProductionStage, ProductionRole, StageResponsibility

        verbose = options["verbose"]
        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for data in RESPONSIBILITIES:
                try:
                    stage = ProductionStage.objects.get(slug=data["stage"])
                except ProductionStage.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  [!] Etapa no encontrada: {data['stage']} — ejecuta seed_production_stages primero."
                        )
                    )
                    continue

                try:
                    responsible_role = ProductionRole.objects.get(name=data["responsible"])
                except ProductionRole.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  [!] Rol no encontrado: {data['responsible']} — ejecuta seed_production_roles primero."
                        )
                    )
                    continue

                responsibility, created = StageResponsibility.objects.get_or_create(
                    stage=stage,
                    defaults={"responsible_role": responsible_role},
                )

                if not created and responsibility.responsible_role != responsible_role:
                    responsibility.responsible_role = responsible_role
                    responsibility.save(update_fields=["responsible_role"])
                    updated_count += 1

                auxiliary_roles = list(
                    ProductionRole.objects.filter(name__in=data["auxiliaries"])
                )
                responsibility.auxiliary_roles.set(auxiliary_roles)

                if created:
                    created_count += 1
                    if verbose:
                        aux_names = ", ".join(r.name for r in auxiliary_roles) or "—"
                        self.stdout.write(
                            f"  [+] {stage.name}: responsable={responsible_role.name}, "
                            f"auxiliares=[{aux_names}]"
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_stage_responsibilities: {created_count} asignadas, "
                f"{updated_count} actualizadas, "
                f"{len(RESPONSIBILITIES) - created_count - updated_count} sin cambios."
            )
        )
