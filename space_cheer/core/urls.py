from django.urls import path
from core import views as core_views
from django.urls import include

urlpatterns = [
    path("", core_views.home, name="dashboard"),
]
