"""
Reglas de convivencia para el alojamiento de menores de edad.

La plataforma maneja datos y ahora también la estancia física de menores, sujeta
a la LGDNNA. Hay dos niveles, y el de la cama es más estricto que el del cuarto:

  HABITACIÓN — un menor la comparte con:
    - su guardián asignado (`AthleteProfile.guardian`), o
    - un adulto acreditado de su equipo: el head coach, o un coach o staff con
      membresía activa y aceptada en un equipo al que el menor pertenece.

  CAMA — un menor solo la comparte con su guardián asignado. Un coach puede
    dormir en el mismo cuarto que una atleta menor, pero no en su misma cama.

Cualquier otro adulto queda fuera. Entre menores no hay restricción, y entre
adultos tampoco.

El módulo importa los modelos de forma perezosa: `hospitality.models` lo usa
desde sus `clean()`, y un import a nivel de módulo sería circular.
"""

import logging

logger = logging.getLogger(__name__)


class MinorLodgingPolicy:

    # -----------------------------------------------------------------
    @staticmethod
    def is_minor(user) -> bool:
        """Delega en el servicio de custodia para no tener dos definiciones
        de 'menor' que puedan separarse.

        Ojo: devuelve False cuando el usuario no tiene fecha de nacimiento.
        Un menor sin `birth_date` registrado no queda protegido por esta regla.
        """
        from custody.services.minor_service import MinorAthleteService

        return MinorAthleteService.is_minor(user)

    # -----------------------------------------------------------------
    @staticmethod
    def accredited_adult_ids(minor, *, include_team_staff=True) -> set:
        """IDs de los adultos que pueden alojarse con este menor.

        `include_team_staff=False` deja solo al guardián: es el criterio para
        compartir cama, más estricto que compartir habitación.
        """
        from accounts.models import AthleteProfile
        from teams.models import Team, UserTeamMembership

        allowed = set()

        # 1. Su guardián asignado.
        profile = AthleteProfile.objects.filter(user=minor).first()
        if profile and profile.guardian_id:
            allowed.add(profile.guardian_id)

        # 2. Cuerpo técnico de sus equipos activos (solo a nivel habitación).
        if not include_team_staff:
            return allowed

        team_ids = list(
            UserTeamMembership.objects.filter(
                user=minor, status="accepted", is_active=True,
            ).values_list("team_id", flat=True)
        )
        if not team_ids:
            return allowed

        allowed.update(
            UserTeamMembership.objects.filter(
                team_id__in=team_ids,
                status="accepted",
                is_active=True,
                role_in_team__in=["HEADCOACH", "COACH", "STAFF"],
            ).values_list("user_id", flat=True)
        )
        # El head coach dueño del equipo vive en Team.coach, que no siempre
        # tiene membresía propia.
        allowed.update(
            Team.objects.filter(pk__in=team_ids).values_list("coach_id", flat=True)
        )
        return allowed

    # -----------------------------------------------------------------
    @classmethod
    def validate_group(cls, users, *, scope="habitación", include_team_staff=True):
        """Levanta ValidationError si algún menor del grupo queda con un adulto
        que no está autorizado a alojarse con él.

        `users` es un iterable de User (sin duplicados relevantes).
        `scope` solo se usa para redactar el mensaje ("habitación" / "cama").
        `include_team_staff=False` restringe a solo el guardián (caso cama).
        """
        from django.core.exceptions import ValidationError

        users = [u for u in users if u is not None]
        if len(users) < 2:
            return

        minors = [u for u in users if cls.is_minor(u)]
        if not minors:
            return

        adults = [u for u in users if not cls.is_minor(u)]
        if not adults:
            return

        for minor in minors:
            allowed = cls.accredited_adult_ids(
                minor, include_team_staff=include_team_staff,
            )
            for adult in adults:
                if adult.pk in allowed:
                    continue
                permitido = (
                    "solo su tutor asignado o el cuerpo técnico de su equipo"
                    if include_team_staff
                    else "solo su tutor asignado"
                )
                raise ValidationError(
                    f"{adult.get_full_name() or adult.username} no puede compartir "
                    f"{scope} con {minor.get_full_name() or minor.username}, que es "
                    f"menor de edad: {permitido} puede hacerlo."
                )

    # -----------------------------------------------------------------
    @classmethod
    def validate_room(cls, room, *, incoming_user=None, exclude_stay_id=None):
        """Valida la composición de una habitación, incluyendo al que va a entrar."""
        from hospitality.models import RoomAssignment, Stay

        qs = (
            RoomAssignment.objects.filter(room=room)
            .exclude(stay__status=Stay.CANCELLED)
            .select_related("stay__user")
        )
        if exclude_stay_id:
            qs = qs.exclude(stay_id=exclude_stay_id)

        ocupantes = [ra.stay.user for ra in qs]
        if incoming_user is not None:
            ocupantes.append(incoming_user)
        cls.validate_group(ocupantes, scope="habitación")

    # -----------------------------------------------------------------
    @classmethod
    def validate_bed(cls, bed, *, incoming_user=None, exclude_stay_id=None):
        """Valida quiénes duermen en una misma cama."""
        from hospitality.models import BedAssignment, Stay

        qs = (
            BedAssignment.objects.filter(bed=bed)
            .exclude(stay__status=Stay.CANCELLED)
            .select_related("stay__user")
        )
        if exclude_stay_id:
            qs = qs.exclude(stay_id=exclude_stay_id)

        ocupantes = [ba.stay.user for ba in qs]
        if incoming_user is not None:
            ocupantes.append(incoming_user)
        # Compartir cama es más estricto que compartir cuarto: un coach
        # acreditado puede dormir en la habitación de una menor, pero no en su
        # misma cama. Ahí solo entra el tutor.
        cls.validate_group(ocupantes, scope="cama", include_team_staff=False)
