"""
Crea los EventStaffRole estándar para competencias de cheerleading.

Uso:
    python manage.py seed_staff_roles
    python manage.py seed_staff_roles --dry-run
    python manage.py seed_staff_roles --verbose

Idempotente: seguro de ejecutar múltiples veces.
"""

from django.core.management.base import BaseCommand
from django.db import transaction


STAFF_ROLES = [
    # ── Seguridad y emergencias ────────────────────────────────────────────
    {
        "name": "Médico",
        "description": "Atención médica de emergencia durante el evento.",
        "is_judge": False,
    },
    {
        "name": "Paramédico",
        "description": "Primeros auxilios y traslado de emergencias.",
        "is_judge": False,
    },
    {
        "name": "Bombero",
        "description": "Control de incendios y evacuación del recinto.",
        "is_judge": False,
    },
    {
        "name": "Seguridad",
        "description": "Control de acceso y orden en el venue.",
        "is_judge": False,
    },
    # ── Logística y operaciones ────────────────────────────────────────────
    {
        "name": "Coordinador General",
        "description": "Responsable de la operación completa del evento.",
        "is_judge": False,
    },
    {
        "name": "Coordinador de Piso",
        "description": "Gestiona el orden de salida y el área de competencia.",
        "is_judge": False,
    },
    {
        "name": "Cronometrador",
        "description": "Controla los tiempos de rutinas y descansos.",
        "is_judge": False,
    },
    {
        "name": "Anotador",
        "description": "Registra y consolida los puntajes de los jueces.",
        "is_judge": False,
    },
    {
        "name": "Recepción y acreditación",
        "description": "Registro de equipos y entrega de credenciales.",
        "is_judge": False,
    },
    {
        "name": "Control de música",
        "description": "Reproducción de las músicas de las rutinas.",
        "is_judge": False,
    },
    {
        "name": "Técnico de sonido",
        "description": "Operación del sistema de audio del venue.",
        "is_judge": False,
    },
    {
        "name": "Técnico de iluminación",
        "description": "Control del sistema de luces durante las rutinas.",
        "is_judge": False,
    },
    {
        "name": "Fotógrafo",
        "description": "Registro fotográfico oficial del evento.",
        "is_judge": False,
    },
    {
        "name": "Videógrafo",
        "description": "Grabación en video oficial del evento.",
        "is_judge": False,
    },
    {
        "name": "Presentador / MC",
        "description": "Conducción del evento frente al público.",
        "is_judge": False,
    },
    {
        "name": "Relaciones públicas",
        "description": "Comunicación con medios y redes sociales.",
        "is_judge": False,
    },
    {
        "name": "Utilero",
        "description": "Manejo de utilería, tapetes y props de equipos.",
        "is_judge": False,
    },
    {
        "name": "Voluntario",
        "description": "Apoyo general en tareas asignadas durante el evento.",
        "is_judge": False,
    },
    # ── Panel de jueces ────────────────────────────────────────────────────
    {
        "name": "Juez Técnico",
        "description": "Evalúa dificultad técnica y ejecución de habilidades.",
        "is_judge": True,
    },
    {
        "name": "Juez de Coreografía",
        "description": "Evalúa creatividad, transiciones y uso del espacio.",
        "is_judge": True,
    },
    {
        "name": "Juez de Sincronización",
        "description": "Evalúa coordinación grupal y timing con la música.",
        "is_judge": True,
    },
    {
        "name": "Juez de Imagen",
        "description": "Evalúa uniformes, presentación y energía del equipo.",
        "is_judge": True,
    },
    {
        "name": "Juez de Seguridad",
        "description": "Penaliza maniobras inseguras o fuera de reglamento.",
        "is_judge": True,
    },
    {
        "name": "Juez Head",
        "description": "Juez principal; resuelve empates y supervisa el panel.",
        "is_judge": True,
    },
]


class Command(BaseCommand):
    help = "Crea los EventStaffRole estándar para competencias de cheerleading"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostrar cambios sin ejecutarlos",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Mostrar detalle de cada rol",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no se guardarán cambios\n"))

        created_count = 0
        updated_count = 0
        ok_count = 0

        with transaction.atomic():
            from events.models import EventStaffRole

            for config in STAFF_ROLES:
                name = config["name"]
                defaults = {k: v for k, v in config.items() if k != "name"}

                role, created = EventStaffRole.objects.get_or_create(
                    name=name, defaults=defaults
                )

                if created:
                    created_count += 1
                    label = self.style.SUCCESS("CREADO")
                else:
                    updated = False
                    for field, value in defaults.items():
                        if getattr(role, field) != value:
                            if not dry_run:
                                setattr(role, field, value)
                            updated = True
                    if updated:
                        if not dry_run:
                            role.save()
                        updated_count += 1
                        label = self.style.WARNING("ACTUALIZADO")
                    else:
                        ok_count += 1
                        label = "OK"

                kind = "Juez" if config["is_judge"] else "Staff"
                if verbose or created:
                    self.stdout.write(f"  [{kind:5}] {name}: {label}")

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            f"\nseed_staff_roles completado — "
            f"{self.style.SUCCESS(f'{created_count} creados')}  "
            f"{self.style.WARNING(f'{updated_count} actualizados')}  "
            f"{ok_count} sin cambios"
        )
