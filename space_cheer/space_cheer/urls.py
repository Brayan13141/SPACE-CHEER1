from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path("admin/", admin.site.urls),
    # Core app URLs
    path("", include("core.urls")),
    # Include allauth and accounts URLs for authentication
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("accounts.urls.views_accounts_urls")),
    path("guardian/", include("accounts.urls.views_guardian_urls")),
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
    path("social/", include("social.urls", namespace="social")),
    path(
        "invitations/",
        include(("invitations.urls", "invitations"), namespace="invitations"),
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
