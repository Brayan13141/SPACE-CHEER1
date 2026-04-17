from django.shortcuts import render
from teams.models import UserTeamMembership


def home(request):
    if request.user.is_authenticated:
        memberships = UserTeamMembership.objects.select_related("team").filter(
            user=request.user, is_active=True, status="accepted"
        ).order_by("team__name")
        teams = [m.team for m in memberships]

        return render(request, "core/dashboard.html", {
            "user_teams": teams,
            "user_teams_count": len(teams),
        })

    return render(request, "core/home.html")


def user_teams_context(request):
    if not request.user.is_authenticated:
        return {}

    memberships = UserTeamMembership.objects.select_related("team").filter(
        user=request.user,
        is_active=True,
        status="accepted",
    ).order_by("team__name")

    teams = [m.team for m in memberships]

    is_headcoach = request.user.roles.filter(name="HEADCOACH").exists()
    is_admin = request.user.roles.filter(name="ADMIN").exists()

    return {
        "navbar_teams": teams,
        "user_teams_count": len(teams),
        "is_headcoach": is_headcoach,
        "is_admin": is_admin,
    }
