from django.urls import path
from core import views as core_views
from django.urls import include

app_name = "core"

urlpatterns = [
    path("", core_views.home, name="dashboard"),
    path("landing/", core_views.landing, name="landing"),
    path("contact/", core_views.contact, name="contact"),
    path("privacy/", core_views.privacy, name="privacy"),
]
