from django.core.exceptions import ValidationError


class OrderContactValidator:

    REQUIRED_FIELDS = [
        "contact_name",
        "contact_phone",
        "contact_email",
        "shipping_address_line",
        "shipping_city",
        "shipping_postal_code",
    ]

    FIELD_LABELS = {
        "contact_name": "Nombre de contacto",
        "contact_phone": "Teléfono",
        "contact_email": "Correo electrónico",
        "shipping_address_line": "Dirección",
        "shipping_city": "Ciudad",
        "shipping_postal_code": "Código postal",
    }

    @classmethod
    def validate_complete(cls, order):

        if not order.has_contact_info():
            raise ValidationError("La orden debe tener información de contacto.")

        contact = order.contact_info

        missing = []

        for field in cls.REQUIRED_FIELDS:
            if not getattr(contact, field):
                missing.append(cls.FIELD_LABELS.get(field, field))

        if missing:
            raise ValidationError(
                f"Faltan campos en la información de contacto: {', '.join(missing)}"
            )
