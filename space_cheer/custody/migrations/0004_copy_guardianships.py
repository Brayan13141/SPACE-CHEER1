"""Copia los vínculos de tutela del modelo viejo al nuevo.

El cuerpo vive en `custody/data_migrations.py` porque la suite corre con
`--nomigrations` y aquí adentro no lo probaría nadie.
"""

from django.db import migrations

from custody.data_migrations import copy_guardianships, restore_athlete_guardian


def adelante(apps, schema_editor):
    copy_guardianships(
        apps.get_model("accounts", "AthleteProfile"),
        apps.get_model("custody", "GuardianProfile"),
        apps.get_model("custody", "Guardianship"),
    )


def atras(apps, schema_editor):
    restore_athlete_guardian(
        apps.get_model("accounts", "AthleteProfile"),
        apps.get_model("custody", "Guardianship"),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("custody", "0003_alter_guardianprofile_verified_by_guardianship"),
        # AthleteProfile.guardian tiene que existir en el estado para poder
        # leerlo: se declara la última migración de accounts a propósito.
        ("accounts", "0015_alter_piiaccesslog_access_type"),
    ]

    operations = [
        migrations.RunPython(adelante, atras),
    ]
