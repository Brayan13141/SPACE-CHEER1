from django.urls import path
from social import views

app_name = "social"

urlpatterns = [
    # Lista
    path("invite/", views.send_invite, name="send_invite"),
]
