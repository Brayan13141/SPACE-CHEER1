# custody/data_migrations.py
"""Cuerpo de la migración de datos de tutela, fuera del RunPython.

La suite corre con `--nomigrations`, así que una migración con la lógica
adentro sería código sin prueba automática justo en la parte irreversible.
Aquí las funciones reciben las clases de modelo por parámetro: la migración
les pasa los históricos de `apps.get_model`, el test los reales.

REGLA: solo campos y atributos `_id`. Los modelos históricos no traen
propiedades, métodos ni `get_FOO_display()`; usarlos daría un test verde y una
migración rota en producción.
"""

RELATION_DEFAULT = "ACOMP"


def copy_guardianships(AthleteProfile, GuardianProfile, Guardianship) -> int:
    """Una fila de `Guardianship` por cada `AthleteProfile` con tutor.

    La relación y la verificación salen del `GuardianProfile` de ese tutor,
    que es donde vivían. Si el tutor no tiene perfil —pasa: el perfil lo creaba
    un signal al asignar el rol, y un tutor cargado por script podía no
    tenerlo— el vínculo nace como acompañante sin respaldo, que es el estado
    más conservador: `ACOMP` no acredita ninguna tutela legal.

    Devuelve cuántos vínculos creó. Es idempotente.
    """
    perfiles = {gp.user_id: gp for gp in GuardianProfile.objects.all()}

    creados = 0
    qs = AthleteProfile.objects.exclude(guardian_id=None).order_by("pk")
    for profile in qs.iterator():
        gp = perfiles.get(profile.guardian_id)
        _, created = Guardianship.objects.get_or_create(
            athlete_id=profile.user_id,
            guardian_id=profile.guardian_id,
            defaults={
                "relation": gp.relation if gp else RELATION_DEFAULT,
                "legal_document": gp.legal_document if gp else "",
                "verified_by_id": gp.verified_by_id if gp else None,
                "verified_at": gp.verified_at if gp else None,
            },
        )
        if created:
            creados += 1
    return creados


def restore_athlete_guardian(AthleteProfile, Guardianship) -> int:
    """Reversa: el vínculo más viejo de cada atleta vuelve al campo único.

    Con N tutores y un solo campo, la reversa PIERDE información por
    definición: se conserva el primero por `created_at` y se descartan los
    demás. Es la reversa correcta para volver al modelo anterior, no una
    restauración fiel.

    Devuelve cuántos perfiles reescribió.
    """
    primeros = {}
    for vinculo in Guardianship.objects.all().order_by("created_at", "pk"):
        primeros.setdefault(vinculo.athlete_id, vinculo.guardian_id)

    restaurados = 0
    for user_id, guardian_id in primeros.items():
        actualizados = AthleteProfile.objects.filter(user_id=user_id).update(
            guardian_id=guardian_id
        )
        restaurados += actualizados

    Guardianship.objects.all().delete()
    return restaurados
