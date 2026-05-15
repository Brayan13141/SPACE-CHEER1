"""
Seed de categorías USASF para TeamCategory.

Estructura:
  All-Star — Mini (N1-2), Youth (N1-3), Junior (N1-4),
             Senior (N1-7), Open (N3-6)
  School   — Prep (N1-4)

Idempotente: usa get_or_create, seguro de ejecutar múltiples veces.

Uso:
    python manage.py seed_categories
    python manage.py seed_categories --verbose
"""

from django.core.management.base import BaseCommand
from teams.models import TeamCategory

# (name, level, description)
CATEGORIES = [
    # ── All-Star · Mini (hasta 8 años) ──────────────────────────────
    ("All-Star Mini Nivel 1", 1, "All-Star · Mini (hasta 8 años) · Nivel 1 USASF"),
    ("All-Star Mini Nivel 2", 2, "All-Star · Mini (hasta 8 años) · Nivel 2 USASF"),
    # ── All-Star · Youth (8-12 años) ────────────────────────────────
    ("All-Star Youth Nivel 1", 1, "All-Star · Youth (8-12 años) · Nivel 1 USASF"),
    ("All-Star Youth Nivel 2", 2, "All-Star · Youth (8-12 años) · Nivel 2 USASF"),
    ("All-Star Youth Nivel 3", 3, "All-Star · Youth (8-12 años) · Nivel 3 USASF"),
    # ── All-Star · Junior (11-14 años) ──────────────────────────────
    ("All-Star Junior Nivel 1", 1, "All-Star · Junior (11-14 años) · Nivel 1 USASF"),
    ("All-Star Junior Nivel 2", 2, "All-Star · Junior (11-14 años) · Nivel 2 USASF"),
    ("All-Star Junior Nivel 3", 3, "All-Star · Junior (11-14 años) · Nivel 3 USASF"),
    ("All-Star Junior Nivel 4", 4, "All-Star · Junior (11-14 años) · Nivel 4 USASF"),
    # ── All-Star · Senior (14+ años) ────────────────────────────────
    ("All-Star Senior Nivel 1", 1, "All-Star · Senior (14+ años) · Nivel 1 USASF"),
    ("All-Star Senior Nivel 2", 2, "All-Star · Senior (14+ años) · Nivel 2 USASF"),
    ("All-Star Senior Nivel 3", 3, "All-Star · Senior (14+ años) · Nivel 3 USASF"),
    ("All-Star Senior Nivel 4", 4, "All-Star · Senior (14+ años) · Nivel 4 USASF"),
    ("All-Star Senior Nivel 5", 5, "All-Star · Senior (14+ años) · Nivel 5 USASF"),
    ("All-Star Senior Nivel 6", 6, "All-Star · Senior (14+ años) · Nivel 6 USASF"),
    ("All-Star Senior Nivel 7", 7, "All-Star · Senior (14+ años) · Nivel 7 USASF"),
    # ── All-Star · Open (cualquier edad) ────────────────────────────
    ("All-Star Open Nivel 3", 3, "All-Star · Open (cualquier edad) · Nivel 3 USASF"),
    ("All-Star Open Nivel 4", 4, "All-Star · Open (cualquier edad) · Nivel 4 USASF"),
    ("All-Star Open Nivel 5", 5, "All-Star · Open (cualquier edad) · Nivel 5 USASF"),
    ("All-Star Open Nivel 6", 6, "All-Star · Open (cualquier edad) · Nivel 6 USASF"),
    # ── School · Prep ───────────────────────────────────────────────
    ("School Prep Nivel 1", 1, "School · Preparatoria · Nivel 1 USASF"),
    ("School Prep Nivel 2", 2, "School · Preparatoria · Nivel 2 USASF"),
    ("School Prep Nivel 3", 3, "School · Preparatoria · Nivel 3 USASF"),
    ("School Prep Nivel 4", 4, "School · Preparatoria · Nivel 4 USASF"),
]


class Command(BaseCommand):
    help = "Crea las categorías USASF estándar (All-Star + School). Idempotente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Mostrar cada categoría creada o ya existente",
        )

    def handle(self, *args, **options):
        verbose = options["verbose"]
        created_count = 0
        existing_count = 0

        for name, level, description in CATEGORIES:
            obj, created = TeamCategory.objects.get_or_create(
                name=name,
                level=level,
                defaults={"description": description},
            )
            if created:
                created_count += 1
                if verbose:
                    self.stdout.write(f"  + {obj}")
            else:
                existing_count += 1
                if verbose:
                    self.stdout.write(f"  = {obj} (ya existe)")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ seed_categories: {created_count} creadas, {existing_count} ya existían "
                f"({len(CATEGORIES)} total)."
            )
        )
