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
    # Puede gestionar equipos/atletas (tiene panel de coach)
    can_manage = is_admin or is_headcoach or is_coach

    return {
        "is_admin": is_admin,
        "is_headcoach": is_headcoach,
        "is_coach": is_coach,
        "is_staff_role": is_staff_role,
        "is_athlete": is_athlete,
        "is_guardian": is_guardian,
        "can_manage": can_manage,
        "user_roles_list": roles,
    }
