# preconditions.py
from dataclasses import dataclass
from orders.models import Order
from orders.services.contactinfo import OrderContactValidator
from django.core.exceptions import ValidationError as DjangoValidationError


@dataclass
class OrderBlockingIssue:
    code: str
    message: str


def can_submit_order(order: Order) -> list[OrderBlockingIssue]:
    issues = []

    if not order.has_contact_info():
        issues.append(
            OrderBlockingIssue(
                code="NO_CONTACT_INFO",
                message="Falta la información de contacto y envío",
            )
        )
    else:
        # Verifica que los campos estén completos
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
        return issues  # sin items no hay más que validar

    items_requiring_athletes = order.items.filter(
        product__usage_type__in=["ATHLETE_CUSTOM", "TEAM_CUSTOM"],
        product__size_strategy="MEASUREMENTS",
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
