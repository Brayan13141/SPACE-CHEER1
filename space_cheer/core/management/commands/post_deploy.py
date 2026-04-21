"""
Comando de post-despliegue: ejecuta migraciones y seeds en el orden correcto.

Uso:
    python manage.py post_deploy
    python manage.py post_deploy --skip-migrate
    python manage.py post_deploy --dry-run
    python manage.py post_deploy --verbose

Pasos en orden:
    1. migrate
    2. seed_roles         (accounts — roles globales del sistema)
    3. seed_staff_roles   (events  — roles de staff/jueces para competencias)
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Post-despliegue: migrate + seeds en orden correcto"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-migrate",
            action="store_true",
            help="Omitir el paso de migrate (útil si ya se corrió por separado)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pasar --dry-run a los seeds (no guarda cambios)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Mostrar detalle de cada operación",
        )

    def handle(self, *args, **options):
        skip_migrate = options["skip_migrate"]
        dry_run = options["dry_run"]
        verbose = options["verbose"]

        steps = []

        if not skip_migrate:
            steps.append(("migrate", [], {}))

        steps += [
            ("seed_roles",       [], {"verbosity": 2 if verbose else 1, "dry_run": dry_run}),
            ("seed_staff_roles", [], {"verbosity": 2 if verbose else 1, "dry_run": dry_run}),
        ]

        total = len(steps)
        for i, (cmd, args_, kwargs) in enumerate(steps, 1):
            self.stdout.write(
                self.style.MIGRATE_HEADING(f"\n[{i}/{total}] {cmd}")
            )
            call_command(cmd, *args_, **kwargs)

        self.stdout.write(self.style.SUCCESS("\npost_deploy completado."))
