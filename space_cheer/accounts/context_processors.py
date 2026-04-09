def user_roles(request):
    if request.user.is_authenticated:
        roles = list(request.user.roles.values_list("name", flat=True))

        return {
            "is_guardian": request.user.roles.filter(name="GUARDIAN").exists(),
            "is_headcoach": request.user.roles.filter(name="HEADCOACH").exists(),
            "is_coach": request.user.roles.filter(name="COACH").exists(),
            "is_admin": request.user.is_superuser
            or request.user.roles.filter(name="ADMIN").exists(),
        }
    return {}
