from orders.models import OrderContactInfo
from accounts.models import UserAddress
from django.core.exceptions import ValidationError


class OrderContactInfoFactory:

    @staticmethod
    def from_user(order, user):

        if not user.email:
            raise ValidationError("El usuario no tiene email registrado")

        full_name = user.get_full_name() or user.username

        default_address = UserAddress.objects.filter(user=user, is_default=True).first()

        return OrderContactInfo(
            order=order,
            contact_name=full_name,
            contact_phone=user.phone or "",
            contact_email=user.email,
            shipping_address_line=default_address.address if default_address else "",
            shipping_city=default_address.city if default_address else "",
            shipping_postal_code=default_address.zip_code if default_address else "",
        )
