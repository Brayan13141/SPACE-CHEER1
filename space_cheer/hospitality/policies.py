"""
Reglas de convivencia para el alojamiento de menores de edad.

La plataforma maneja datos y ahora también la estancia física de menores, sujeta
a la LGDNNA. Hay dos niveles, y el de la cama es más estricto que el del cuarto:

  HABITACIÓN — un menor la comparte con:
    - cualquiera de sus tutores acreditados (`custody.Guardianship`), o
    - un adulto acreditado de su equipo: el head coach, o un coach o staff con
      membresía activa y aceptada en un equipo al que el menor pertenece.

  CAMA — un menor solo comparte cama con alguno de sus tutores. Un coach puede
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
        """¿Hay que proteger a esta persona como menor?

        Parte de `MinorAthleteService.is_minor`, para no tener dos definiciones
        de "menor" que puedan separarse, pero cierra su punto ciego: ese
        servicio devuelve False cuando no hay `birth_date`, y una regla de
        protección que se apaga sola ante un dato faltante no protege nada.

        Aquí, **un atleta sin fecha de nacimiento cuenta como menor**. Es el
        lado seguro del error: como mucho exige que su tutor o el cuerpo
        técnico sean quienes lo acompañen, y se corrige llenando su fecha.

        Un no-atleta sin fecha sigue contando como adulto, y por lo tanto tiene
        que estar acreditado para alojarse con un menor: por ese lado la falta
        de dato ya era restrictiva, no permisiva.
        """
        from accounts.models import AthleteProfile
        from custody.services.minor_service import MinorAthleteService

        if MinorAthleteService.is_minor(user):
            return True
        if user.birth_date is None:
            return AthleteProfile.objects.filter(user=user).exists()
        return False

    # -----------------------------------------------------------------
    @staticmethod
    def accredited_adult_ids(minor, *, include_team_staff=True) -> set:
        """IDs de los adultos que pueden alojarse con este menor.

        `include_team_staff=False` deja solo a sus tutores: es el criterio para
        compartir cama, más estricto que compartir habitación.
        """
        from custody.models import Guardianship
        from teams.models import Team, UserTeamMembership

        allowed = set()

        # 1. Sus tutores acreditados. Son N y valen todos por igual: los tres
        # tipos de relación (padre/madre, tutor legal, acompañante) autorizan
        # lo mismo, igual que cuando el tutor era uno solo.
        allowed.update(
            Guardianship.objects.filter(athlete=minor).values_list(
                "guardian_id", flat=True
            )
        )

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

        # Los roles de membresía se toman de ROLE_CHOICES, no de literales:
        # "HEADCOACH" NO es un valor válido del modelo (solo ATHLETE, COACH y
        # STAFF lo son), así que filtrar por él acreditaba a quien tuviera ese
        # valor escrito fuera de spec, sin que el modelo lo reconozca.
        roles_validos = {code for code, _ in UserTeamMembership.ROLE_CHOICES}
        roles_tecnicos = sorted(roles_validos - {"ATHLETE"})

        allowed.update(
            UserTeamMembership.objects.filter(
                team_id__in=team_ids,
                status="accepted",
                is_active=True,
                role_in_team__in=roles_tecnicos,
            ).values_list("user_id", flat=True)
        )
        # El head coach es el dueño del equipo (Team.coach), no un valor de
        # role_in_team: esa es la única fuente de verdad para ese cargo.
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
                    "solo sus tutores o el cuerpo técnico de su equipo"
                    if include_team_staff
                    else "solo sus tutores"
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

    # -----------------------------------------------------------------
    @classmethod
    def audit_stay(cls, stay):
        """Revalida una estancia YA asignada contra el estado actual.

        La validación de `clean()` decide en el momento de asignar y ese
        resultado queda congelado en la fila. Si después se le quita el tutor
        al menor, o el coach deja el equipo, la habitación sigue asignada y
        nadie vuelve a mirar. Esto es lo que rompe ese supuesto.

        Devuelve la lista de mensajes de incumplimiento (vacía si todo bien),
        en vez de levantar: sirve para auditar en bloque sin cortar al primero.
        """
        from django.core.exceptions import ValidationError
        from hospitality.models import Stay

        if stay.status == Stay.CANCELLED:
            return []

        problemas = []
        room_assignment = getattr(stay, "room_assignment", None)
        if room_assignment is not None:
            try:
                cls.validate_room(room_assignment.room)
            except ValidationError as exc:
                problemas.extend(exc.messages)

        for bed_assignment in stay.bed_assignments.select_related("bed"):
            try:
                cls.validate_bed(bed_assignment.bed)
            except ValidationError as exc:
                problemas.extend(exc.messages)

        return problemas

    # -----------------------------------------------------------------
    @classmethod
    def audit_event(cls, event):
        """Todas las estancias vivas de un evento que hoy incumplen la regla.

        Devuelve {stay: [mensajes]}. Pensado para que administración pueda
        detectar los alojamientos que quedaron inválidos por un cambio
        posterior de tutela o de equipo.
        """
        from hospitality.models import Stay

        resultado = {}
        estancias = (
            Stay.objects.filter(event=event)
            .exclude(status=Stay.CANCELLED)
            .select_related("user", "room_assignment__room")
        )
        for stay in estancias:
            problemas = cls.audit_stay(stay)
            if problemas:
                resultado[stay] = problemas
        return resultado
