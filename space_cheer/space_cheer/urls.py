from django.contrib import admin
from django.urls import include, path
from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Include allauth and accounts URLs for authentication
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("accounts.urls")),
    # Core app URLs
    path("", include("core.urls")),
    # teams
    path("teams/", include("teams.urls")),
    # Measures
    path("measures/", include("measures.urls")),
    # coach
    path("coach/", include("coach.urls")),
]
