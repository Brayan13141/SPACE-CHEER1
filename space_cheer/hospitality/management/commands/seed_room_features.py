"""
Crea las RoomFeature estándar para hoteles de eventos de cheerleading.

Uso:
    python manage.py seed_room_features
    python manage.py seed_room_features --dry-run
    python manage.py seed_room_features --verbose

Idempotente: seguro de ejecutar múltiples veces.
"""

from django.core.management.base import BaseCommand
from django.db import transaction


ROOM_FEATURES = [
    # ── Conectividad ──────────────────────────────────────────────────────────
    {"name": "WiFi",                "icon": "bi-wifi"},
    {"name": "WiFi de alta velocidad", "icon": "bi-wifi"},
    # ── Climatización ─────────────────────────────────────────────────────────
    {"name": "Aire acondicionado",  "icon": "bi-thermometer-snow"},
    {"name": "Calefacción",         "icon": "bi-thermometer-sun"},
    # ── Entretenimiento ───────────────────────────────────────────────────────
    {"name": "Televisión",          "icon": "bi-tv"},
    {"name": "TV por cable",        "icon": "bi-tv-fill"},
    # ── Baño ──────────────────────────────────────────────────────────────────
    {"name": "Baño privado",        "icon": "bi-droplet"},
    {"name": "Bañera",              "icon": "bi-droplet-fill"},
    {"name": "Artículos de tocador","icon": "bi-bag"},
    # ── Camas y ropa de cama ──────────────────────────────────────────────────
    {"name": "Ropa de cama incluida", "icon": "bi-stars"},
    {"name": "Almohadas extra",     "icon": "bi-moon"},
    # ── Alimentación ──────────────────────────────────────────────────────────
    {"name": "Desayuno incluido",   "icon": "bi-cup-hot"},
    {"name": "Cafetera",            "icon": "bi-cup-hot-fill"},
    {"name": "Minibar",             "icon": "bi-cup-straw"},
    {"name": "Cocina equipada",     "icon": "bi-house-gear"},
    {"name": "Microondas",          "icon": "bi-lightning-charge"},
    {"name": "Refrigerador",        "icon": "bi-snow"},
    # ── Instalaciones del hotel ───────────────────────────────────────────────
    {"name": "Alberca",             "icon": "bi-water"},
    {"name": "Gimnasio",            "icon": "bi-activity"},
    {"name": "Spa",                 "icon": "bi-heart-pulse"},
    {"name": "Restaurante",         "icon": "bi-cup-straw"},
    {"name": "Bar",                 "icon": "bi-cup"},
    {"name": "Sala de eventos",     "icon": "bi-people"},
    # ── Servicios ─────────────────────────────────────────────────────────────
    {"name": "Servicio a cuartos",  "icon": "bi-bell"},
    {"name": "Caja fuerte",         "icon": "bi-shield-lock"},
    {"name": "Estacionamiento",     "icon": "bi-car-front"},
    {"name": "Estacionamiento gratuito", "icon": "bi-car-front-fill"},
    {"name": "Servicio de lavandería", "icon": "bi-bucket"},
    {"name": "Plancha",             "icon": "bi-tools"},
    {"name": "Secadora de cabello", "icon": "bi-wind"},
    {"name": "Escritorio de trabajo", "icon": "bi-pencil-square"},
    # ── Accesibilidad ─────────────────────────────────────────────────────────
    {"name": "Accesible para personas con discapacidad", "icon": "bi-person-wheelchair"},
    {"name": "Elevador",            "icon": "bi-building-up"},
    # ── Política ──────────────────────────────────────────────────────────────
    {"name": "No fumadores",        "icon": "bi-slash-circle"},
    {"name": "Admite mascotas",     "icon": "bi-heart"},
    # ── Vistas ────────────────────────────────────────────────────────────────
    {"name": "Vista al jardín",     "icon": "bi-tree"},
    {"name": "Vista a la ciudad",   "icon": "bi-buildings"},
    {"name": "Balcón",              "icon": "bi-door-open"},
]


class Command(BaseCommand):
    help = "Crea las RoomFeature estándar para hoteles de eventos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostrar cambios sin ejecutarlos",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Mostrar detalle de cada característica",
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
            from hospitality.models import RoomFeature

            for config in ROOM_FEATURES:
                name = config["name"]
                icon = config["icon"]

                feature, created = RoomFeature.objects.get_or_create(
                    name=name,
                    defaults={"icon": icon},
                )

                if created:
                    created_count += 1
                    label = self.style.SUCCESS("CREADO")
                else:
                    if feature.icon != icon:
                        if not dry_run:
                            feature.icon = icon
                            feature.save()
                        updated_count += 1
                        label = self.style.WARNING("ACTUALIZADO")
                    else:
                        ok_count += 1
                        label = "OK"

                if verbose or created:
                    self.stdout.write(f"  {name}: {label}")

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            f"\nseed_room_features completado — "
            f"{self.style.SUCCESS(f'{created_count} creadas')}  "
            f"{self.style.WARNING(f'{updated_count} actualizadas')}  "
            f"{ok_count} sin cambios"
        )
