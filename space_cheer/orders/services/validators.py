from django.core.exceptions import ValidationError
from teams.models import UserTeamMembership


class OrderBaseValidator:
    @staticmethod
    def validate_owner(order):
        """
        Valida que la orden tenga un dueño válido según su tipo
        """
        if order.order_type == "PERSONAL":
            if not order.owner_user:
                raise ValidationError(
                    "Las órdenes personales deben tener un dueño (usuario)"
                )
            if order.owner_team:
                raise ValidationError(
                    "Las órdenes personales no pueden tener un equipo asignado"
                )
        elif order.order_type == "TEAM":
            if not order.owner_team:
                raise ValidationError(
                    "Las órdenes de equipo deben tener un equipo asignado"
                )
            if order.owner_user:
                raise ValidationError(
                    "Las órdenes de equipo no pueden tener un dueño usuario"
                )
        else:
            raise ValidationError("Tipo de orden no válido")

    @staticmethod
    def validate_contact(order):
        if not order.pk:
            raise ValidationError(
                "Debe existir una orden guardada antes de validar su contacto"
            )

        if not hasattr(order, "contact_info"):
            raise ValidationError("La orden no tiene información de contacto")

        order.contact_info.full_clean()


class OrderAthleteValidator:
    @staticmethod
    def validate_athlete_for_order(order, athlete):
        """
        Valida si un atleta puede ser asociado a una orden
        """

        # 1. La orden debe ser editable
        if not order.can_edit_general():
            raise ValidationError(
                "No se pueden modificar atletas en una orden que no está en borrador"
            )

        # 2. Orden PERSONAL
        if order.order_type == "PERSONAL":
            if athlete != order.owner_user:
                raise ValidationError(
                    "En órdenes personales solo se puede asignar al dueño de la orden"
                )

        # 3. Orden de EQUIPO
        elif order.order_type == "TEAM":
            if not UserTeamMembership.objects.filter(
                user=athlete,
                team=order.owner_team,
                status="accepted",
                is_active=True,
                role_in_team="ATLETA",
            ).exists():
                raise ValidationError("El usuario no es atleta activo del equipo")

        else:
            raise ValidationError("Tipo de orden no válido")

    @staticmethod
    def validate_not_duplicated(order_item, athlete):
        """
        Evita que el mismo atleta se agregue dos veces al mismo item
        """
        if order_item.athletes.filter(athlete=athlete).exists():
            raise ValidationError(
                f"El atleta {athlete} ya está asignado a este producto"
            )


class OrderDesignValidator:
    @staticmethod
    def validate(order):

        if not order.pk:
            raise ValidationError("No hay orden guardada para validar el diseño")

        if not order.items.exists():
            raise ValidationError("El pedido no tiene productos")

        # Debe existir al menos un diseño
        if not order.design_images.exists():
            raise ValidationError("La orden no tiene diseños cargados")

        # Debe existir un diseño final
        if not order.design_images.filter(is_final=True).exists():
            raise ValidationError("Debe existir un diseño marcado como final")


class OrderMeasurementsValidator:
    @staticmethod
    def validate_complete(order):

        items = (
            order.items.filter(product__size_strategy="MEASUREMENTS")
            .select_related("product")
            .prefetch_related(
                "athletes__measurements",
                "product__measurement_fields",
            )
        )

        errors = []

        for item in items:
            for athlete_item in item.athletes.all():
                if not athlete_item.has_complete_measurements():
                    errors.append(
                        f"Faltan medidas para el atleta {athlete_item.athlete} "
                        f"en {item.product.name}"
                    )

        if errors:
            raise ValidationError("\n".join(errors))
