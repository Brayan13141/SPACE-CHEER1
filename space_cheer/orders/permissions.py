# orders/services/permissions.py

from django.core.exceptions import PermissionDenied
from accounts.models import UserOwnership
import logging

logger = logging.getLogger(__name__)


class OrderPermissions:
    """
    Clase centralizada para permisos de órdenes.
    """

    @staticmethod
    def _has_admin_access(user):
        """Verifica acceso de administrador."""
        return user.is_superuser or user.roles.filter(name="ADMIN").exists()

    @staticmethod
    def can_manage_order(user, order):
        """
        Verifica si un usuario puede gestionar una orden específica.
        """

        # Administradores pueden gestionar todo
        if OrderPermissions._has_admin_access(user):
            return True

        if order.created_by == user:
            return True

        # Dueño de orden personal
        if order.order_type == "PERSONAL":
            if order.owner_user == user:
                return True

            # Usuarios que gestionan al dueño (coaches)
            if UserOwnership.objects.filter(
                owner=user, user=order.owner_user, is_active=True
            ).exists():
                return True

        # Miembros de equipo para órdenes de equipo
        elif order.order_type == "TEAM":
            if order.owner_team.memberships.filter(
                user=user,
                status="accepted",
                is_active=True,
                role_in_team__in=["HEADCOACH", "STAFF"],
            ).exists():
                return True

        return False

    @staticmethod
    def can_approve_design(user, order):
        """
        Verifica si un usuario puede aprobar diseños de una orden.
        """
        # Staff/Admin siempre pueden aprobar
        if OrderPermissions._has_admin_access(user):
            return True

        # Dueño de orden personal
        if order.order_type == "PERSONAL":
            return order.owner_user == user

        # Para equipos: entrenadores
        if order.order_type == "TEAM":
            membership = order.owner_team.memberships.filter(
                user=user, status="accepted", is_active=True
            ).first()

            if membership:
                # Solo roles específicos pueden aprobar diseños
                return membership.role_in_team == "HEADCOACH"

        return False

    @staticmethod
    def can_cancel_order(user, order):
        """
        Verifica si un usuario puede cancelar una orden.
        """
        # Solo se puede cancelar en estados iniciales
        if order.status not in ["DRAFT", "PENDING", "DESIGN_APPROVED"]:
            return False

        return OrderPermissions.can_manage_order(user, order)

    @staticmethod
    def can_view_order(user, order):
        """
        Verifica si un usuario puede ver una orden.
        """
        # Admin ve todo
        if OrderPermissions._has_admin_access(user):
            return True

        # Miembros del equipo pueden ver órdenes del equipo
        if order.order_type == "TEAM":
            return order.owner_team.memberships.filter(
                user=user, status="accepted", is_active=True
            ).exists()

        # Usuario ve sus órdenes personales
        if order.order_type == "PERSONAL":
            return (
                order.owner_user == user
                or UserOwnership.objects.filter(
                    owner=user, user=order.owner_user, is_active=True
                ).exists()
            )

        return False


# Funciones de conveniencia para compatibilidad
def can_manage_order(user, order):
    return OrderPermissions.can_manage_order(user, order)


def can_approve_design(user, order):
    return OrderPermissions.can_approve_design(user, order)
