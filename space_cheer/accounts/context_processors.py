def user_roles(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user
    roles = list(user.roles.values_list("name", flat=True))

    is_admin = user.is_superuser or "ADMIN" in roles
    is_headcoach = "HEADCOACH" in roles
    is_coach = "COACH" in roles
    is_staff_role = "STAFF" in roles
    is_athlete = "ATHLETE" in roles
    is_guardian = "GUARDIAN" in roles
    is_operario = "OPERARIO" in roles
    is_juez = "JUEZ" in roles
    # Puede gestionar equipos/atletas (tiene panel de coach)
    can_manage = is_admin or is_headcoach or is_coach
    # Operario sin ningún otro rol: navbar simplificado solo con producción
    is_only_operario = is_operario and len(roles) == 1

    unread = user.notifications.filter(read=False)
    # Campanas separadas: gestión excluye sociales, la social solo cuenta SOCIAL_*
    unread_notifications_count = unread.exclude(
        notification_type__startswith="SOCIAL_"
    ).count()
    unread_social_count = unread.filter(
        notification_type__startswith="SOCIAL_"
    ).count()

    return {
        "is_admin": is_admin,
        "is_headcoach": is_headcoach,
        "is_coach": is_coach,
        "is_staff_role": is_staff_role,
        "is_athlete": is_athlete,
        "is_guardian": is_guardian,
        "is_operario": is_operario,
        "is_juez": is_juez,
        "is_only_operario": is_only_operario,
        "can_manage": can_manage,
        "user_roles_list": roles,
        "unread_notifications_count": unread_notifications_count,
        "unread_social_count": unread_social_count,
    }
