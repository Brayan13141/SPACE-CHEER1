# custody/services/minor_service.py
"""
Servicio para gestión de atletas menores de edad.

Reglas de negocio:
- Un atleta menor DEBE tener al menos un tutor acreditado
- El coach que posee al atleta (o un ADMIN) da de alta y de baja los vínculos
- Los tutores de un atleta son iguales entre sí: no hay tutor "principal"
- La relación y la verificación viven en el VÍNCULO, no en el tutor: la misma
  persona puede ser madre de una atleta y tutora legal de otra
- Si el atleta cumple 18 años, puede quedarse sin ningún tutor
"""

import logging
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import AthleteProfile, UserOwnership
from custody.models import Guardianship

logger = logging.getLogger(__name__)
User = get_user_model()


class MinorAthleteService:
    """
    Gestiona el ciclo de vida de atletas menores de edad:
    - Validación de edad
    - Alta y baja de vínculos de tutela
    - Verificación de compliance (menor sin ningún tutor = bloqueado)
    """

    # =========================================================================
    # VALIDACIONES PÚBLICAS
    # =========================================================================

    @staticmethod
    def is_minor(user: User) -> bool:
        """
        Determina si un usuario es menor de edad.
        Retorna False si no tiene fecha de nacimiento registrada.
        """
        if not user.birth_date:
            return False

        today = timezone.now().date()
        age = (
            today.year
            - user.birth_date.year
            - ((today.month, today.day) < (user.birth_date.month, user.birth_date.day))
        )
        return age < 18

    @staticmethod
    def requires_guardian(athlete: User) -> bool:
        """
        Retorna True si el atleta es menor Y no tiene NINGÚN tutor acreditado.
        Esto define si el sistema debe bloquear ciertas operaciones.
        """
        if not MinorAthleteService.is_minor(athlete):
            return False

        if not AthleteProfile.objects.filter(user=athlete).exists():
            return True

        return not Guardianship.objects.filter(athlete=athlete).exists()

    @staticmethod
    def is_guardian_of(guardian: User, athlete: User) -> bool:
        """¿Existe un vínculo de tutela acreditado entre estos dos?

        Predicado único: por acá pasa todo el resto del sistema. No mira la
        edad del atleta a propósito — quien la necesite la comprueba aparte,
        exactamente como hoy.
        """
        if guardian is None or athlete is None:
            return False
        if guardian.pk is None or athlete.pk is None:
            return False
        return Guardianship.objects.filter(
            athlete=athlete, guardian=guardian,
        ).exists()

    @staticmethod
    def get_guardians(athlete: User):
        """Los tutores del atleta (queryset de User, puede venir vacío)."""
        return User.objects.filter(guardianships_held__athlete=athlete).distinct()

    @staticmethod
    def get_guardianships(athlete: User):
        """Los vínculos del atleta, con su relación y su estado de verificación.

        `get_guardians` devuelve User y ahí no se ve si el vínculo está
        verificado: eso es del par. Las pantallas usan esta.
        """
        return (
            Guardianship.objects.filter(athlete=athlete)
            .select_related("guardian", "verified_by")
        )

    # =========================================================================
    # ALTA Y BAJA DE VÍNCULOS
    # =========================================================================

    @staticmethod
    @transaction.atomic
    def assign_guardian(
        *,
        athlete: User,
        guardian: User,
        assigned_by: User,
        relation: str = Guardianship.ACOMP,
    ) -> Guardianship:
        """
        Acredita a un tutor más para un atleta menor. NO reemplaza a los demás.

        Idempotente: si el vínculo ya existe, actualiza su relación con las
        mismas reglas que `update_guardian_relation`.

        Lanza:
            ValidationError si las reglas de negocio no se cumplen
            PermissionDenied si el usuario no tiene permiso
        """
        MinorAthleteService._validate_can_manage_athlete(assigned_by, athlete)

        valid_relations = {code for code, _ in Guardianship.RELATION_CHOICES}
        if relation not in valid_relations:
            raise ValidationError(
                f"Relación inválida: {relation}. Opciones: {valid_relations}"
            )

        if not AthleteProfile.objects.filter(user=athlete).exists():
            raise ValidationError(
                f"El atleta {athlete} no tiene perfil de atleta. "
                "Crea el perfil primero."
            )

        if not MinorAthleteService.is_minor(athlete):
            raise ValidationError(
                f"El atleta {athlete} no es menor de edad. "
                "Los guardians solo se asignan a menores."
            )

        if guardian == athlete:
            raise ValidationError("Un atleta no puede ser su propio guardian.")

        # Fecha de nacimiento obligatoria: `is_minor()` responde False cuando
        # falta, así que sin este corte un usuario sin fecha pasaba el filtro
        # de "no es menor" por omisión del dato, no por ser mayor.
        if guardian.birth_date is None:
            raise ValidationError(
                f"El usuario {guardian} no tiene fecha de nacimiento registrada. "
                "No se puede confirmar que sea mayor de edad."
            )

        if MinorAthleteService.is_minor(guardian):
            raise ValidationError(
                f"El usuario {guardian} también es menor de edad "
                "y no puede ser guardian."
            )

        # El filtro por rol vivía solo en el desplegable de la vista, así que
        # el admin de Django, un script o un comando asignaban como guardian a
        # cualquier usuario. La regla pertenece al servicio.
        if not guardian.roles.filter(name="GUARDIAN").exists():
            raise ValidationError(
                f"El usuario {guardian} no tiene el rol GUARDIAN. "
                "Asígnale el rol antes de ponerlo como tutor."
            )

        existente = Guardianship.objects.filter(
            athlete=athlete, guardian=guardian,
        ).first()
        if existente is not None:
            if existente.relation != relation:
                return MinorAthleteService.update_guardian_relation(
                    athlete=athlete,
                    guardian=guardian,
                    relation=relation,
                    updated_by=assigned_by,
                )
            return existente

        vinculo = Guardianship.objects.create(
            athlete=athlete,
            guardian=guardian,
            relation=relation,
            created_by=assigned_by,
        )

        logger.info(
            "Tutor %s acreditado para el atleta menor %s como %s por %s",
            guardian, athlete, relation, assigned_by,
        )
        return vinculo

    @staticmethod
    @transaction.atomic
    def remove_guardian(*, athlete: User, guardian: User, removed_by: User) -> None:
        """
        Quita UN vínculo de tutela. Los demás vínculos del atleta, y los del
        mismo tutor con otros atletas, quedan intactos.

        Un menor no puede quedarse sin ninguno: el último vínculo solo se
        suelta cuando el atleta ya es mayor de edad.
        """
        MinorAthleteService._validate_can_manage_athlete(removed_by, athlete)

        vinculo = Guardianship.objects.filter(
            athlete=athlete, guardian=guardian,
        ).first()
        if vinculo is None:
            return  # Idempotente

        es_el_ultimo = Guardianship.objects.filter(athlete=athlete).count() == 1
        if es_el_ultimo and MinorAthleteService.is_minor(athlete):
            raise ValidationError(
                f"No se puede quitar a {guardian} porque es el único tutor de "
                f"{athlete}, que sigue siendo menor de edad. Acredita a otro "
                "tutor antes de quitar este."
            )

        vinculo.delete()

        logger.info(
            "Vínculo de tutela %s → %s removido por %s",
            guardian, athlete, removed_by,
        )

    @staticmethod
    @transaction.atomic
    def update_guardian_relation(
        *, athlete: User, guardian: User, relation: str, updated_by: User
    ) -> Guardianship:
        """Actualiza el tipo de relación de UN vínculo (PADRE, TUTOR, ACOMP)."""
        # Las opciones salen del modelo: dos listas de lo mismo se separan.
        VALID_RELATIONS = {code for code, _ in Guardianship.RELATION_CHOICES}

        if relation not in VALID_RELATIONS:
            raise ValidationError(
                f"Relación inválida: {relation}. Opciones: {VALID_RELATIONS}"
            )

        MinorAthleteService._validate_can_manage_athlete(updated_by, athlete)

        vinculo = Guardianship.objects.filter(
            athlete=athlete, guardian=guardian,
        ).first()
        if vinculo is None:
            raise ValidationError(f"{guardian} no es tutor de {athlete}.")

        relacion_anterior = vinculo.relation
        vinculo.relation = relation
        campos = ["relation"]

        # Cambiar lo que se declara invalida la verificación anterior: se
        # revisó un vínculo distinto del que ahora se afirma. Aplica SOLO a
        # este vínculo — los demás del mismo tutor no se tocan.
        if relacion_anterior != relation and vinculo.is_verified:
            vinculo.verified_by = None
            vinculo.verified_at = None
            vinculo.legal_document = ""
            campos += ["verified_by", "verified_at", "legal_document"]
            logger.info(
                "Verificación del vínculo %s → %s invalidada: la relación pasó "
                "de %s a %s",
                guardian, athlete, relacion_anterior, relation,
            )

        vinculo.save(update_fields=campos)
        return vinculo

    # =========================================================================
    # VERIFICACIÓN DEL RESPALDO
    # =========================================================================

    @staticmethod
    @transaction.atomic
    def verify_guardianship(
        *, guardianship: Guardianship, verified_by: User, legal_document: str = "",
    ) -> Guardianship:
        """Deja constancia de que alguien revisó el respaldo de una tutela legal.

        No sube archivos: registra la referencia del documento y, sobre todo,
        QUIÉN dio el visto bueno y CUÁNDO. Eso es lo que convierte una casilla
        de formulario en algo auditable.

        Recibe el VÍNCULO, no el tutor: verificar la tutela legal sobre una
        atleta no dice nada de los otros atletas del mismo tutor.
        """
        if not (verified_by.is_superuser
                or verified_by.roles.filter(name="ADMIN").exists()):
            raise PermissionDenied(
                "Solo un administrador puede verificar una tutela legal."
            )

        if not guardianship.requires_proof:
            raise ValidationError(
                f"La relación '{guardianship.get_relation_display()}' no requiere "
                "verificación documental."
            )

        guardianship.legal_document = legal_document
        guardianship.verified_by = verified_by
        guardianship.verified_at = timezone.now()
        guardianship.save(
            update_fields=["legal_document", "verified_by", "verified_at"]
        )

        logger.info(
            "Tutela legal de %s sobre %s verificada por %s (documento=%s)",
            guardianship.guardian, guardianship.athlete, verified_by,
            legal_document or "sin referencia",
        )
        return guardianship

    @staticmethod
    def guardians_needing_attention(guardians=None):
        """Vínculos con tutela legal sin verificar, o de tutores sobrecargados.

        Devuelve [(vínculo, [motivos])]. Es para mostrar, no para bloquear.
        """
        qs = Guardianship.objects.select_related("guardian", "athlete")
        if guardians is not None:
            qs = qs.filter(guardian__in=guardians)

        resultado = []
        for vinculo in qs:
            motivos = []
            if vinculo.proof_pending:
                motivos.append("declara tutela legal sin verificar")
            if vinculo.over_soft_limit:
                motivos.append(
                    f"tiene {Guardianship.athlete_count_for(vinculo.guardian)} "
                    "atletas a cargo"
                )
            if motivos:
                resultado.append((vinculo, motivos))
        return resultado

    # =========================================================================
    # QUERIES DE CONVENIENCIA
    # =========================================================================

    @staticmethod
    def get_minors_without_guardian(coach: User):
        """Atletas menores SIN ningún tutor, con scope según rol del coach."""
        owned_ids = UserOwnership.objects.filter(
            owner=coach,
            is_active=True,
        ).values_list("user_id", flat=True)

        today = timezone.now().date()
        cutoff_date = today.replace(year=today.year - 18)

        base = User.objects.filter(
            roles__name="ATHLETE",
            birth_date__isnull=False,
            birth_date__lte=today,
            birth_date__gt=cutoff_date,
        ).filter(
            Q(athleteprofile__isnull=True) | Q(guardianships__isnull=True)
        )

        if coach.is_superuser or coach.roles.filter(name="ADMIN").exists():
            return base.select_related("athleteprofile").distinct()
        elif coach.roles.filter(name="HEADCOACH").exists():
            return (
                base.filter(id__in=owned_ids)
                .select_related("athleteprofile")
                .distinct()
            )
        else:
            raise PermissionDenied("No tienes permisos para ver esta información.")

    @staticmethod
    def get_all_minors(coach: User):
        """Retorna TODOS los atletas menores, tengan o no tutor."""
        owned_ids = UserOwnership.objects.filter(
            owner=coach,
            is_active=True,
        ).values_list("user_id", flat=True)

        today = timezone.now().date()
        cutoff_date = today.replace(year=today.year - 18)

        base = User.objects.filter(
            roles__name="ATHLETE",
            birth_date__isnull=False,
            birth_date__lte=today,
            birth_date__gt=cutoff_date,
        )

        if coach.is_superuser or coach.roles.filter(name="ADMIN").exists():
            return (
                base.select_related("athleteprofile")
                .prefetch_related("guardianships__guardian")
                .distinct()
            )
        elif coach.roles.filter(name="HEADCOACH").exists():
            return (
                base.filter(id__in=owned_ids)
                .select_related("athleteprofile")
                .prefetch_related("guardianships__guardian")
                .distinct()
            )
        else:
            raise PermissionDenied("No tienes permisos para ver esta información.")

    @staticmethod
    def get_athletes_for_guardian(guardian: User):
        """Retorna todos los atletas que tienen a este usuario como tutor."""
        return (
            User.objects.filter(guardianships__guardian=guardian)
            .select_related("athleteprofile")
            .distinct()
        )

    @staticmethod
    def guardians_present_at(event, athlete: User):
        """Tutores del atleta con estancia viva en ese evento.

        Es la respuesta a "quién viajó con esta atleta", como CONSULTA y no
        como dato guardado: una designación por viaje se desincronizaría con
        las estancias reales y dejaría dos fuentes de verdad en desacuerdo.
        """
        from hospitality.models import Stay

        ids = (
            Stay.objects.filter(event=event)
            .exclude(status=Stay.CANCELLED)
            .values_list("user_id", flat=True)
        )
        return (
            User.objects.filter(guardianships_held__athlete=athlete, id__in=ids)
            .distinct()
        )

    # =========================================================================
    # HELPERS PRIVADOS
    # =========================================================================

    @staticmethod
    def _validate_can_manage_athlete(manager: User, athlete: User):
        """
        Verifica que `manager` tiene permiso para gestionar al `athlete`.
        - Admin/superuser → siempre puede
        - HEADCOACH → solo atletas que le pertenecen (UserOwnership)
        """
        if manager.is_superuser:
            return

        if manager.roles.filter(name="ADMIN").exists():
            return

        if manager.roles.filter(name="HEADCOACH").exists():
            owns = UserOwnership.objects.filter(
                owner=manager,
                user=athlete,
                is_active=True,
            ).exists()

            if not owns:
                raise PermissionDenied(
                    f"No tienes permiso para gestionar al atleta {athlete}."
                )
            return

        raise PermissionDenied("No tienes permisos para gestionar atletas.")
