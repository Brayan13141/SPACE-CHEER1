from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from orders.models import Order, OrderLog
import logging
from django.db import transaction
from orders.permissions import can_manage_order
from orders.permissions import can_approve_design
from orders.services.validators import OrderDesignValidator
from orders.services.preconditions import can_submit_order
from orders.services.validators import OrderBaseValidator
from orders.services.validators import OrderMeasurementsValidator
from orders.services.contactinfo import OrderContactValidator


logger = logging.getLogger(__name__)


class OrderStateService:
    """
    Servicio para manejar transiciones de estado de órdenes.
    Maneja validaciones, efectos secundarios y logging.
    """

    # Efectos secundarios por cada transición
    STATE_EFFECTS = {
        "DESIGN_APPROVED": {
            "measurements_locked": True,
            "locked_at": True,  # True significa usar timezone.now()
            "design_approved_by": "user",
            "design_approved_at": True,
        },
        "IN_PRODUCTION": {
            "production_started_at": True,
        },
        "DELIVERED": {
            "delivered_at": True,
            "closed": True,
        },
        "CANCELLED": {
            "closed": True,
            "cancelled_at": True,
            "cancelled_by": "user",
        },
    }

    @classmethod
    def can_transition(cls, order, to_status):
        """Verifica si una transición está permitida basada en el estado actual."""
        return to_status in order.ALLOWED_TRANSITIONS.get(order.status, [])

    @classmethod
    def validate_transition(cls, order, to_status, user):
        """
        Valida todos los aspectos de una transición antes de ejecutarla.
        """
        # 1. Validar transición permitida
        if not cls.can_transition(order, to_status):
            raise ValidationError(
                f"Transición no permitida desde {order.status} a {to_status}"
            )

        # 2. Validar permisos del usuario
        if not cls._can_user_transition(user, order, to_status):
            raise PermissionDenied(
                f"El usuario no tiene permisos para cambiar la orden a {to_status}"
            )

        # 3. Validaciones específicas por estado
        validation_method = getattr(cls, f"_validate_to_{to_status.lower()}", None)

        if validation_method:
            validation_method(order)

    @classmethod
    def _apply_state_effects(cls, order, to_status, user, notes, extra_kwargs):

        effects = cls.STATE_EFFECTS.get(to_status, {})
        now = timezone.now()

        for field, value in effects.items():

            if value is True and field.endswith("_at"):
                setattr(order, field, now)

            elif value is True:
                setattr(order, field, True)

            elif value == "user":
                setattr(order, field, user)

            elif value == "notes":
                setattr(order, field, notes)

            elif field in extra_kwargs:
                setattr(order, field, extra_kwargs[field])

        # Optimización: update directo
        if to_status in ["CANCELLED", "DELIVERED"]:
            if hasattr(order, "contact_info") and order.contact_info:
                order.contact_info.closed = True
                order.contact_info.save(update_fields=["closed"])

        if to_status == "CANCELLED":
            order.cancelled_reason = notes or "Cancelado por el usuario"

    @classmethod
    @transaction.atomic
    def transition(cls, order, to_status, user, notes="", **kwargs):
        # ── Paso 1: lock solo sobre la tabla Order ──────────────────────
        Order.objects.select_for_update().filter(pk=order.pk).get()

        # ── Paso 2: fetch completo con relaciones SIN select_for_update ─
        order = (
            Order.objects.select_related("owner_team", "owner_user")
            .prefetch_related(
                "items",
                "items__product",
                "items__athletes__measurements",
                "design_images",
            )
            .get(pk=order.pk)
        )
        from_status = order.status

        cls.validate_transition(order, to_status, user)

        cls._apply_state_effects(order, to_status, user, notes, kwargs)
        order.status = to_status
        order.updated_at = timezone.now()

        cls._persist_transition(order)

        cls._create_transition_log(order, user, from_status, to_status, notes)

        cls._post_transition_hooks(order, from_status, to_status, user)

        return order

    @classmethod
    def _persist_transition(cls, order):
        order._allow_status_change = True
        order.save(
            update_fields=[
                "status",
                "updated_at",
                "measurements_locked",
                "locked_at",
                "design_approved_by",
                "design_approved_at",
                "production_started_at",
                "delivered_at",
                "closed",
                "cancelled_at",
                "cancelled_by",
                "cancelled_reason",
            ]
        )

    @classmethod
    def _can_user_transition(cls, user, order, to_status):

        # 👑 Superuser puede todo
        if user.is_superuser:
            return True

        # 👨‍💼 Staff puede todo
        if user.is_staff:
            return True

        # Cancelar o enviar a pending → creador
        if to_status in ["PENDING", "CANCELLED"]:
            return can_manage_order(user, order)

        # Aprobar diseño
        if to_status == "DESIGN_APPROVED":
            return can_approve_design(user, order)

        # Producción / Entrega solo staff
        if to_status in ["IN_PRODUCTION", "DELIVERED"]:
            return False

        return False

    @classmethod
    def get_available_transitions(cls, order, user):

        available = []

        for potential_status in order.ALLOWED_TRANSITIONS.get(order.status, []):

            # -----------------------------------------
            # FILTRO DE DISEÑO
            # -----------------------------------------

            # Si la orden NO requiere diseño, ocultar DESIGN_APPROVED
            if potential_status == "DESIGN_APPROVED" and not order.requires_design:
                continue

            # Si la orden SÍ requiere diseño, no permitir saltar a producción
            if potential_status == "IN_PRODUCTION" and order.requires_design:
                if order.status == "PENDING":
                    continue

            # -----------------------------------------
            # VALIDACIÓN DE PERMISOS
            # -----------------------------------------

            if cls.can_user_attempt_transition(order, potential_status, user):
                available.append(potential_status)

        return available

    @classmethod
    def can_user_attempt_transition(cls, order, to_status, user):
        """
        Verificación ligera para UI.
        No ejecuta validaciones pesadas.
        """
        if not cls.can_transition(order, to_status):
            return False

        if not cls._can_user_transition(user, order, to_status):
            return False

        return True

    @classmethod
    def _validate_to_pending(cls, order):
        # ── Validaciones de contenido (ya existen) ──
        order.validate_order_ready(order)

        for item in order.items.select_related("product").all():
            if order.order_type == "TEAM":
                if (
                    item.product.scope == "TEAM_ONLY"
                    and item.product.owner_team != order.owner_team
                ):
                    raise ValidationError("Producto no pertenece al equipo de la orden")

        issues = can_submit_order(order)

        if order.total <= 0:
            raise ValidationError("La orden no tiene total válido")

        if issues:
            raise ValidationError(
                {"blocking_issues": [issue.message for issue in issues]}
            )

        # ── Fecha requerida para confirmar ──────────────────────────────
        if not order.freeze_payment_date:
            raise ValidationError(
                "Debe registrarse el pago de congelación antes de enviar la orden."
            )

    @classmethod
    def _validate_to_design_approved(cls, order):

        from teams.models import UserTeamMembership

        items = list(
            order.items.select_related("product").prefetch_related("athletes__athlete")
        )

        if not items:
            raise ValidationError("La orden no tiene productos")

        # -------------------------------------------------
        # VALIDAR DISEÑO SOLO SI ALGÚN PRODUCTO LO REQUIERE
        # -------------------------------------------------

        requires_design = any(item.product.requires_design for item in items)

        if requires_design:
            if not order.design_images.filter(is_final=True).exists():
                raise ValidationError("Se requiere una imagen de diseño final")

        # -------------------------------------------------
        # OBTENER ATLETAS DEL EQUIPO (solo rol ATLETA)
        # -------------------------------------------------

        team_athletes = set()

        if order.order_type == "TEAM":
            team_athletes = set(
                UserTeamMembership.objects.filter(
                    team=order.owner_team,
                    status="accepted",
                    is_active=True,
                    role_in_team="ATLETA",
                ).values_list("user_id", flat=True)
            )

        # -------------------------------------------------
        # VALIDAR ATLETAS POR ITEM
        # -------------------------------------------------

        for item in items:

            product = item.product

            if not product.requires_athletes:
                continue

            athletes = list(item.athletes.all())

            if not athletes:
                raise ValidationError(
                    f"El producto '{product.name}' requiere atletas asignados"
                )

            # -----------------------------------------
            # VALIDAR CONSISTENCIA CON EL EQUIPO
            # -----------------------------------------

            if order.order_type == "TEAM":

                item_athletes = set(a.athlete_id for a in athletes)

                if item_athletes != team_athletes:

                    missing = team_athletes - item_athletes
                    extra = item_athletes - team_athletes

                    if missing:
                        raise ValidationError(
                            f"Faltan atletas del equipo en el producto '{product.name}'"
                        )

                    if extra:
                        raise ValidationError(
                            f"Hay atletas asignados al producto '{product.name}' que no pertenecen al equipo"
                        )

        # -------------------------------------------------
        # VALIDAR MEDIDAS SOLO SI SE REQUIEREN
        # -------------------------------------------------

        requires_measurements = any(
            item.product.requires_measurements for item in items
        )

        if requires_measurements:
            OrderMeasurementsValidator.validate_complete(order)

        # -------------------------------------------------
        # VALIDACIÓN DE DISEÑO (si aplica)
        # -------------------------------------------------

        if requires_design:
            OrderDesignValidator.validate(order)

    @classmethod
    def _validate_to_in_production(cls, order):
        items = list(order.items.select_related("product"))

        if not items:
            raise ValidationError("La orden no tiene productos")

        requires_design = any(item.product.requires_design for item in items)
        if requires_design:
            if not order.design_images.filter(is_final=True).exists():
                raise ValidationError("No hay diseño final aprobado")

        requires_measurements = any(
            item.product.requires_measurements for item in items
        )
        if requires_measurements and not order.measurements_locked:
            raise ValidationError("Las medidas deben estar bloqueadas")

        # ── Fechas requeridas para iniciar producción ────────────────────
        if not order.measurements_due_date:
            raise ValidationError(
                "Debe establecerse la fecha límite de entrega de medidas."
            )

        if not order.uniform_delivery_date:
            raise ValidationError(
                "Debe establecerse la fecha de entrega del uniforme antes de iniciar producción."
            )

        # La regla measurements_due_date <= uniform_delivery_date
        # ya la valida Order.clean() cuando el staff edita las fechas.
        # Aquí solo verificamos que ambas existan.

    @classmethod
    def _validate_to_delivered(cls, order):
        # ── Fecha requerida para marcar como entregada ───────────────────
        if not order.final_payment_date:
            raise ValidationError(
                "Debe registrarse el pago final antes de marcar como entregada."
            )

        if not order.uniform_delivery_date:
            raise ValidationError("Debe establecer la fecha de entrega del uniforme.")

    @classmethod
    def _create_transition_log(cls, order, user, from_status, to_status, notes):
        """Crea un registro de log para auditoría."""
        OrderLog.objects.create(
            order=order,
            user=user,
            action="STATUS_CHANGE",
            from_status=from_status,
            to_status=to_status,
            notes=notes,
            metadata={
                "measurements_locked": order.measurements_locked,
                "locked_at": order.locked_at.isoformat() if order.locked_at else None,
            },
        )

    @classmethod
    def _post_transition_hooks(cls, order, from_status, to_status, user):
        """Hooks para acciones post-transición (notificaciones, etc.)"""
        # Aquí puedes agregar notificaciones por email, webhooks, etc.
        if to_status == "DESIGN_APPROVED":
            cls._notify_design_approved(order, user)
        elif to_status == "IN_PRODUCTION":
            cls._notify_production_started(order, user)
        elif to_status == "DELIVERED":
            cls._notify_order_delivered(order, user)

    # NOTIFICACIONES
    @classmethod
    def _notify_design_approved(cls, order, user):
        """Envía notificación cuando el diseño es aprobado."""
        # TODO: Implementar notificaciones por email o sistema de mensajes
        pass

    @classmethod
    def _notify_production_started(cls, order, user):
        """Envía notificación cuando la producción comienza."""
        pass

    @classmethod
    def _notify_order_delivered(cls, order, user):
        """Envía notificación cuando la orden es entregada."""
        pass


class OrderCreationService:

    @staticmethod
    @transaction.atomic
    def create_order(*, order_type, created_by, owner_user=None, owner_team=None):
        """
        Crea una orden aplicando todas las reglas de dominio.
        """

        order = Order(
            order_type=order_type,
            created_by=created_by,
            owner_user=owner_user,
            owner_team=owner_team,
        )
        # Validación explícita de dominio
        OrderBaseValidator.validate_owner(order)

        order.save()

        OrderLog.objects.create(
            order=order,
            user=created_by,
            action="ORDER_CREATED",
            from_status="",
            to_status="DRAFT",
            metadata={"order_type": order_type},
        )

        return order
