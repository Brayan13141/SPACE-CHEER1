"""
Ejecuta todos los seeds de datos iniciales en el orden correcto.

Orden:
  1. seed_roles          — Roles de usuario (ADMIN, COACH, ATHLETE, etc.)
  2. seed_staff_roles    — Roles de staff para eventos (jueces, coordinadores, etc.)
  3. seed_room_features  — Características de habitaciones para hospitalidad

Uso:
    python manage.py seed_all
    python manage.py seed_all --dry-run
    python manage.py seed_all --verbose
    python manage.py seed_all --only roles
    python manage.py seed_all --only staff_roles
    python manage.py seed_all --only room_features

Idempotente: seguro de ejecutar múltiples veces.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


SEEDS = [
    {
        "key": "roles",
        "command": "seed_roles",
        "label": "Roles de usuario",
    },
    {
        "key": "staff_roles",
        "command": "seed_staff_roles",
        "label": "Roles de staff para eventos",
    },
    {
        "key": "room_features",
        "command": "seed_room_features",
        "label": "Características de habitaciones",
    },
    {
        "key": "categories",
        "command": "seed_categories",
        "label": "Categorías USASF (All-Star + School)",
    },
    {
        "key": "production_stages",
        "command": "seed_production_stages",
        "label": "Etapas de producción",
    },
    {
        "key": "production_roles",
        "command": "seed_production_roles",
        "label": "Roles base de producción",
    },
]


class Command(BaseCommand):
    help = "Ejecuta todos los seeds de datos iniciales en orden"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pasar --dry-run a cada seed sin guardar cambios",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Pasar --verbose a cada seed",
        )
        parser.add_argument(
            "--only",
            type=str,
            metavar="SEED",
            help=f"Ejecutar solo un seed específico: {', '.join(s['key'] for s in SEEDS)}",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        only = options.get("only")

        seeds_to_run = SEEDS
        if only:
            seeds_to_run = [s for s in SEEDS if s["key"] == only]
            if not seeds_to_run:
                valid = ", ".join(s["key"] for s in SEEDS)
                self.stderr.write(
                    self.style.ERROR(f"Seed desconocido: '{only}'. Válidos: {valid}")
                )
                return

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no se guardarán cambios\n"))

        for seed in seeds_to_run:
            self.stdout.write(
                self.style.MIGRATE_HEADING(f"\n▶  {seed['label']} ({seed['command']})")
            )
            kwargs = {}
            if dry_run:
                kwargs["dry_run"] = True
            if verbose:
                kwargs["verbosity"] = 2
            call_command(seed["command"], **kwargs)

        self.stdout.write(self.style.SUCCESS("\n✓  seed_all completado."))
