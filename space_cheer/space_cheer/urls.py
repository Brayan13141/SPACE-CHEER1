from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from core.views_media import serve_protected_media

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    # Core app URLs
    path("", include("core.urls")),
    # Include allauth and accounts URLs for authentication
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("accounts.urls.views_accounts_urls")),
    path("guardian/", include("custody.urls")),
    # teams
    path("teams/", include("teams.urls")),
    # Measures
    path("measures/", include("measures.urls")),
    # coach
    path("coach/", include("coach.urls")),
    # orders
    path("orders/", include("orders.urls")),
    # products
    path("products/", include("products.urls")),
    # events
    path("events/", include("events.urls", namespace="events")),
    # hospitality
    path("hospitality/", include("hospitality.urls", namespace="hospitality")),
    path("social/", include("social.urls", namespace="social")),
    path(
        "invitations/",
        include(("invitations.urls", "invitations"), namespace="invitations"),
    ),
]

urlpatterns += [
    path("media/<path:path>", serve_protected_media, name="protected_media"),
]
