from django.db import transaction
from django.db.models import Q

from orders.models import Order
from orders.services.state import OrderCreationService
from orders.services.factories import OrderContactInfoFactory
from products.models import Product
from teams.models import Team


class CartService:

    @staticmethod
    @transaction.atomic
    def get_or_create_draft(*, user, order_type: str, team=None) -> Order:
        """
        Returns existing DRAFT order or creates a new one.
        Creates contact info for new orders following the same pattern as create_order view.
        """
        if order_type == 'PERSONAL':
            order = Order.objects.filter(
                order_type='PERSONAL',
                owner_user=user,
                status='DRAFT',
            ).first()
            if order:
                return order
            order = OrderCreationService.create_order(
                order_type='PERSONAL',
                created_by=user,
                owner_user=user,
            )

        elif order_type == 'TEAM':
            if team is None:
                raise ValueError("team is required for TEAM orders")
            order = Order.objects.filter(
                order_type='TEAM',
                owner_team=team,
                status='DRAFT',
            ).first()
            if order:
                return order
            order = OrderCreationService.create_order(
                order_type='TEAM',
                created_by=user,
                owner_team=team,
            )

        else:
            raise ValueError(f"Invalid order_type: {order_type}")

        try:
            contact_info = OrderContactInfoFactory.from_user(order=order, user=user)
            contact_info.full_clean()
            contact_info.save()
        except Exception:
            pass

        return order

    @staticmethod
    def get_catalog_queryset(user):
        """
        Returns Product queryset visible to the user in the catalog.
        Users with teams see all CATALOG products + TEAM_ONLY for their teams.
        Users without teams see only CATALOG + usage_type=GLOBAL.
        """
        base = (
            Product.objects
            .filter(is_active=True, is_configured=True, season__is_active=True)
            .select_related('season', 'owner_team')
            .prefetch_related('size_variants')
        )

        user_teams = Team.objects.filter(coach=user)
        if user_teams.exists():
            team_ids = user_teams.values_list('pk', flat=True)
            return base.filter(
                Q(scope='CATALOG') |
                Q(scope='TEAM_ONLY', owner_team__in=team_ids)
            ).order_by('product_type', 'name')

        return base.filter(
            scope='CATALOG',
            usage_type='GLOBAL',
        ).order_by('name')
