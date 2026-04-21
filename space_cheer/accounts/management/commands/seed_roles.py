# accounts/management/commands/seed_roles.py
"""
Management command para:
1. Crear rol JUEZ (inactivo — para Events futuro)
2. Consolidar ACOMPANANTE → GUARDIAN (migrar usuarios existentes)
3. Crear NotificationPreferences y PrivacySettings para usuarios existentes

Uso:
    python manage.py seed_roles
    python manage.py seed_roles --dry-run   # preview sin cambios
    python manage.py seed_roles --verbose   # detalle de cada operación

Seguro de ejecutar múltiples veces (idempotente).
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Seed roles y migra datos de ACOMPANANTE → GUARDIAN"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostrar cambios sin ejecutarlos",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Mostrar detalle de cada operación",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no se guardarán cambios"))

        with transaction.atomic():
            self._seed_roles(dry_run, verbose)
            self._create_missing_preferences(dry_run, verbose)

            if dry_run:
                # Rollback en dry_run
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("seed_roles completado."))

    def _seed_roles(self, dry_run, verbose):
        """Crea o actualiza los 7 roles definitivos."""
        from accounts.models import Role

        # Definición completa de roles
        # allow_dashboard_access=False para JUEZ: no tiene dashboard todavía
        roles_config = [
            {
                "name": "ADMIN",
                "requires_curp": False,
                "is_staff_type": True,
                "is_athlete_type": False,
                "is_coach_type": False,
                "allow_dashboard_access": True,
            },
            {
                "name": "HEADCOACH",
                "requires_curp": True,
                "is_staff_type": False,
                "is_athlete_type": False,
                "is_coach_type": True,
                "allow_dashboard_access": True,
            },
            {
                "name": "COACH",
                "requires_curp": True,
                "is_staff_type": False,
                "is_athlete_type": False,
                "is_coach_type": True,
                "allow_dashboard_access": True,
            },
            {
                "name": "STAFF",
                "requires_curp": True,
                "is_staff_type": True,
                "is_athlete_type": False,
                "is_coach_type": False,
                "allow_dashboard_access": True,
            },
            {
                "name": "ATHLETE",
                "requires_curp": True,
                "is_staff_type": False,
                "is_athlete_type": True,
                "is_coach_type": False,
                "allow_dashboard_access": True,
            },
            {
                "name": "GUARDIAN",
                "requires_curp": True,
                "is_staff_type": False,
                "is_athlete_type": False,
                "is_coach_type": False,
                "allow_dashboard_access": True,
            },
            {
                "name": "JUEZ",
                "requires_curp": True,
                "is_staff_type": False,
                "is_athlete_type": False,
                "is_coach_type": False,
                "is_judge_type": True,
                "allow_dashboard_access": True,
            },
        ]

        for config in roles_config:
            name = config.pop("name")
            role, created = Role.objects.get_or_create(name=name, defaults=config)

            if not created:
                # Actualizar campos si ya existía
                updated = False
                for field, value in config.items():
                    if getattr(role, field) != value:
                        if not dry_run:
                            setattr(role, field, value)
                        updated = True

                if updated and not dry_run:
                    role.save()

            action = "CREADO" if created else ("ACTUALIZADO" if updated else "OK")
            if verbose or created:
                self.stdout.write(f"  Rol {name}: {action}")

    def _create_missing_preferences(self, dry_run, verbose):
        """
        Crea NotificationPreferences y PrivacySettings para todos
        los usuarios que no los tienen.
        """
        from accounts.models import NotificationPreferences, PrivacySettings

        users_without_notif = User.objects.filter(notification_preferences__isnull=True)
        count_notif = users_without_notif.count()

        users_without_privacy = User.objects.filter(privacy_settings__isnull=True)
        count_privacy = users_without_privacy.count()

        self.stdout.write(
            f"  Creando NotificationPreferences para {count_notif} usuarios"
        )
        self.stdout.write(f"  Creando PrivacySettings para {count_privacy} usuarios")

        if not dry_run:
            # Bulk create es más eficiente para miles de usuarios
            NotificationPreferences.objects.bulk_create(
                [NotificationPreferences(user=u) for u in users_without_notif],
                ignore_conflicts=True,
            )
            PrivacySettings.objects.bulk_create(
                [PrivacySettings(user=u) for u in users_without_privacy],
                ignore_conflicts=True,
            )
