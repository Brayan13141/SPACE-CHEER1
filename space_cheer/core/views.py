from django.shortcuts import render
from teams.models import UserTeamMembership
from django.contrib.auth.decorators import login_required


@login_required
def home(request):
    IsAdm = (
        request.user.roles.filter(name="ADMIN").exists()
        or request.user.roles.filter(name="HEADCOACH").exists()
    )
    return render(
        request,
        "core/home.html",
        {
            "roles": IsAdm,
        },
    )


def user_teams_context(request):
    if not request.user.is_authenticated:
        return {}

    memberships = UserTeamMembership.objects.select_related("team").filter(
        user=request.user,
        is_active=True,
        status="accepted",
    )

    teams = [m.team for m in memberships]

    is_headcoach = request.user.roles.filter(name="HEADCOACH").exists()
    is_admin = request.user.roles.filter(name="ADMIN").exists()

    return {
        "navbar_teams": teams,
        "user_teams_count": len(teams),
        "is_headcoach": is_headcoach,
        "is_admin": is_admin,
    }
