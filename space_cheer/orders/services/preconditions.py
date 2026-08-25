# preconditions.py
from dataclasses import dataclass
from orders.models import Order
from orders.services.contactinfo import OrderContactValidator
from orders.services.validators import OrderMeasurementsValidator
from django.core.exceptions import ValidationError as DjangoValidationError


# Quién tiene que resolver el pendiente. El head coach necesita distinguir lo
# suyo de lo que espera de administración: sin esto, un pedido detenido se ve
# igual esté esperándolo a él o no.
OWNER_COACH = "COACH"
OWNER_ADMIN = "ADMIN"
OWNER_TALLER = "TALLER"

OWNER_LABELS = {
    OWNER_COACH: "Te toca a ti",
    OWNER_ADMIN: "Lo resuelve administración",
    OWNER_TALLER: "Está en manos del taller",
}


@dataclass
class OrderBlockingIssue:
    code: str
    message: str
    owner: str = OWNER_COACH
    hint: str = ""

    @property
    def owner_label(self):
        return OWNER_LABELS.get(self.owner, "")

    @property
    def is_mine(self):
        return self.owner == OWNER_COACH


def can_submit_order(order: Order) -> list[OrderBlockingIssue]:
    """Colecciona todos los bloqueos (no solo el primero) que impiden enviar un
    Order a producción: falta info de contacto, sin items, o items CUSTOM sin
    atletas asignados. Lista vacía = el pedido puede transicionar."""
    issues = []

    if not order.has_contact_info():
        issues.append(
            OrderBlockingIssue(
                code="NO_CONTACT_INFO",
                message="Falta la información de contacto y envío",
            )
        )
    else:
        try:
            OrderContactValidator.validate_complete(order)
        except DjangoValidationError as e:
            issues.append(
                OrderBlockingIssue(
                    code="INCOMPLETE_CONTACT_INFO",
                    message=", ".join(e.messages),
                )
            )

    if not order.items.exists():
        issues.append(
            OrderBlockingIssue(
                code="NO_ITEMS",
                message="El pedido no tiene productos agregados",
            )
        )
        return issues

    # ✅ Ahora filtra igual que la view: usage_type en CUSTOM
    items_requiring_athletes = order.items.filter(
        product__usage_type__in=["ATHLETE_CUSTOM", "TEAM_CUSTOM"],
    )

    if items_requiring_athletes.exists():
        items_without_athletes = items_requiring_athletes.filter(
            athletes__isnull=True
        ).distinct()

        if items_without_athletes.exists():
            product_names = list(
                items_without_athletes.values_list("product__name", flat=True)
            )
            issues.append(
                OrderBlockingIssue(
                    code="NO_ATHLETES_ASSIGNED",
                    message=(
                        f"Los siguientes productos requieren atletas asignados: "
                        f"{', '.join(product_names)}"
                    ),
                )
            )

    return issues


# ---------------------------------------------------------------------------
# QUÉ FALTA PARA EL SIGUIENTE PASO
# ---------------------------------------------------------------------------

# El siguiente estado "natural" de cada uno, ignorando la cancelación.
NEXT_STATUS = {
    "DRAFT": "PENDING",
    "PENDING": "DESIGN_APPROVED",
    "DESIGN_APPROVED": "IN_PRODUCTION",
    "IN_PRODUCTION": "DELIVERED",
}

NEXT_STATUS_LABELS = {
    "PENDING": "enviar el pedido",
    "DESIGN_APPROVED": "aprobar el diseño",
    "IN_PRODUCTION": "iniciar producción",
    "DELIVERED": "marcar como entregado",
}


def next_step_requirements(order: Order) -> list[OrderBlockingIssue]:
    """Todo lo que falta para que el pedido avance al siguiente estado.

    `can_submit_order` solo mira el salto DRAFT → PENDING. Esto cubre el ciclo
    entero, porque el problema no era que faltara la validación —los
    `_validate_to_*` de OrderStateService la hacen— sino que solo hablaba
    cuando alguien ya había intentado avanzar, y de a un error por vez.

    Espeja a propósito esos validadores. Si cambian, esto tiene que cambiar
    con ellos: aquí se anuncia, allá se impide.

    Devuelve lista vacía si el pedido puede avanzar (o si ya está en un estado
    final).
    """
    to_status = NEXT_STATUS.get(order.status)
    if to_status is None:
        return []

    items = list(order.items.select_related("product"))
    requires_design = any(i.product.requires_design for i in items)
    requires_measurements = any(i.product.requires_measurements for i in items)
    has_uniforms = any(i.product.product_type == "UNIFORM" for i in items)
    is_offline = order.order_type == "OFFLINE"

    issues = []

    def falta(code, message, owner=OWNER_COACH, hint=""):
        issues.append(
            OrderBlockingIssue(code=code, message=message, owner=owner, hint=hint)
        )

    # ── DRAFT → PENDING ──────────────────────────────────────────────
    if to_status == "PENDING":
        if is_offline:
            if not order.items.exists():
                falta("NO_ITEMS", "El pedido no tiene productos", OWNER_ADMIN)
            if not order.agreed_price or order.agreed_price <= 0:
                falta("NO_AGREED_PRICE",
                      "Falta registrar el precio acordado", OWNER_ADMIN)
            return issues

        try:
            Order.validate_order_ready(order)
        except DjangoValidationError as e:
            for msg in e.messages:
                falta("ORDER_NOT_READY", msg)
        issues.extend(can_submit_order(order))
        if requires_design and not order.freeze_payment_date:
            falta(
                "NO_FREEZE_PAYMENT",
                "Falta registrar el pago de congelación",
                OWNER_ADMIN,
                "Este pedido lleva diseño personalizado, y ese pago reserva el "
                "lugar en el calendario de producción.",
            )
        return issues

    # ── PENDING → DESIGN_APPROVED ────────────────────────────────────
    if to_status == "DESIGN_APPROVED":
        if not items:
            falta("NO_ITEMS", "El pedido no tiene productos")
            return issues
        if requires_design and not order.design_images.filter(is_final=True).exists():
            falta(
                "NO_FINAL_DESIGN",
                "Falta subir el diseño final",
                OWNER_ADMIN,
                "Mientras no haya un arte marcado como final, el pedido no puede "
                "aprobarse.",
            )
        if requires_measurements and not is_offline:
            try:
                OrderMeasurementsValidator.validate_complete(order)
            except DjangoValidationError as e:
                for msg in e.messages:
                    falta(
                        "INCOMPLETE_MEASUREMENTS", msg, OWNER_COACH,
                        "Captura las medidas que faltan desde la ficha de cada atleta.",
                    )
        return issues

    # ── DESIGN_APPROVED → IN_PRODUCTION ──────────────────────────────
    if to_status == "IN_PRODUCTION":
        if not items:
            falta("NO_ITEMS", "El pedido no tiene productos")
            return issues
        if requires_design and not order.design_images.filter(is_final=True).exists():
            falta("NO_FINAL_DESIGN", "No hay diseño final aprobado", OWNER_ADMIN)

        if requires_measurements and not is_offline:
            if not order.measurements_due_date:
                falta("NO_MEASURES_DUE_DATE",
                      "Falta la fecha límite de entrega de medidas", OWNER_ADMIN)
            if not order.measurements_locked:
                falta(
                    "MEASURES_NOT_LOCKED",
                    "Falta bloquear las medidas",
                    OWNER_ADMIN,
                    "Aprobar el diseño solo cierra la captura; el bloqueo es una "
                    "acción aparte y es definitiva: después ya nadie puede "
                    "corregir una medida.",
                )
        if has_uniforms and not order.uniform_delivery_date:
            falta("NO_DELIVERY_DATE",
                  "Falta la fecha de entrega del uniforme", OWNER_ADMIN)
        if not is_offline and not order.first_payment_date:
            falta("NO_FIRST_PAYMENT",
                  "Falta registrar el primer pago", OWNER_ADMIN)
        return issues

    # ── IN_PRODUCTION → DELIVERED ────────────────────────────────────
    if to_status == "DELIVERED":
        from production.models import ProductionJob, ProductionTask

        job = ProductionJob.objects.filter(order=order).first()
        if job is not None:
            pendientes = (
                ProductionTask.objects.filter(job=job)
                .exclude(status=ProductionTask.Status.COMPLETED)
                .count()
            )
            if pendientes:
                falta(
                    "PRODUCTION_PENDING",
                    f"Quedan {pendientes} etapa(s) de producción sin completar",
                    OWNER_TALLER,
                )
        if is_offline:
            if order.payment_status != "LIQUIDADO":
                falta("NOT_PAID_OFF",
                      "Falta liquidar el saldo del pedido", OWNER_ADMIN)
        elif requires_design and not order.final_payment_date:
            falta("NO_FINAL_PAYMENT",
                  "Falta registrar el pago final", OWNER_ADMIN)
        if has_uniforms and not order.uniform_delivery_date:
            falta("NO_DELIVERY_DATE",
                  "Falta la fecha de entrega del uniforme", OWNER_ADMIN)
        return issues

    return issues


# Lo que ve un cliente cuando el pendiente no es suyo. No menciona pagos,
# bloqueos ni etapas de taller: cómo se organiza Space Cheer por dentro no es
# asunto de quien encarga el pedido, y detallarlo invita a preguntar por qué
# su pedido lleva tres días en la misma etapa.
GENERIC_INTERNAL_MESSAGE = (
    "El equipo de Space Cheer está trabajando en este pedido. "
    "Te avisaremos en cuanto avance."
)


def visible_requirements(order: Order, viewer) -> tuple[list, bool]:
    """Los pendientes que `viewer` puede ver, y si hay otros que no.

    Quien administra pedidos (admin y staff) los ve todos con su detalle: es
    su trabajo. El cliente ve **solo lo suyo** —tiene que poder actuar sobre
    ello— y del resto sabe únicamente que el pedido está en curso.

    Devuelve (lista_visible, hay_pendientes_internos).
    """
    from orders.permissions import can_administer_orders

    requisitos = next_step_requirements(order)
    if can_administer_orders(viewer):
        return requisitos, False

    propios = [r for r in requisitos if r.is_mine]
    ajenos = [r for r in requisitos if not r.is_mine]
    return propios, bool(ajenos)
