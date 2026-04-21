# accounts/services/user_search_service.py
"""
Servicio de búsqueda de usuarios para coaches y admins.

Reglas de visibilidad:
- ADMIN/superuser: busca en todos los usuarios
- HEADCOACH: busca solo en sus owned users + usuarios sin owner
- La búsqueda nunca expone CURP, datos médicos ni dirección

Uso:
    results = UserSearchService.search(
        query="ana garcia",
        searching_user=request.user,
        role_filter="ATHLETE",
        exclude_ids=[1, 2, 3],
    )
"""

import logging
from django.db.models import Q
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class UserSearchService:
    """
    Búsqueda segura de usuarios respetando el aislamiento entre coaches.
    """

    SAFE_FIELDS = [
        "id",
        "username",
        "first_name",
        "last_name",
        "email",
        "phone",
        "birth_date",
        "foto_perfil",
    ]

    @staticmethod
    def search(
        *,
        query: str,
        searching_user,
        role_filter: str = None,
        exclude_ids: list = None,
        limit: int = 20,
    ):
        """
        Busca usuarios por nombre, username o email.

        Parámetros:
            query: texto a buscar (mínimo 2 caracteres)
            searching_user: usuario que hace la búsqueda (determina scope)
            role_filter: nombre de rol para filtrar (ej: "ATHLETE")
            exclude_ids: IDs a excluir del resultado (ej: ya agregados)
            limit: máximo de resultados (default 20)

        Retorna QuerySet[User] con solo campos seguros.
        """
        query = query.strip()

        if len(query) < 2:
            return User.objects.none()

        # --- Base queryset según permisos ---
        base_qs = UserSearchService._get_base_queryset(searching_user)

        # --- Filtro de búsqueda (nombre, email, username) ---
        search_filter = (
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(username__icontains=query)
        )

        qs = base_qs.filter(search_filter, is_active=True)

        # --- Filtro por rol ---
        if role_filter:
            qs = qs.filter(roles__name=role_filter)

        # --- Excluir IDs ---
        if exclude_ids:
            qs = qs.exclude(id__in=exclude_ids)

        return (
            qs.select_related()
            .prefetch_related("roles")
            .only(*UserSearchService.SAFE_FIELDS)
            .distinct()
            .order_by("first_name", "last_name")[:limit]
        )

    @staticmethod
    def _get_base_queryset(searching_user):
        """
        Determina el scope de búsqueda según el rol del usuario.
        """
        from accounts.models import UserOwnership

        # Admin y superuser buscan en todos
        if (
            searching_user.is_superuser
            or searching_user.roles.filter(name="ADMIN").exists()
        ):
            return User.objects.all()

        # HEADCOACH: solo sus owned users
        if searching_user.roles.filter(name="HEADCOACH").exists():
            owned_ids = UserOwnership.objects.filter(
                owner=searching_user,
                is_active=True,
            ).values_list("user_id", flat=True)

            return User.objects.filter(id__in=owned_ids)

        # Cualquier otro: solo ellos mismos
        return User.objects.filter(id=searching_user.id)
