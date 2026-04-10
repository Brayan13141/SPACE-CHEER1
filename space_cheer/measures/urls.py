from django.urls import path
from .views import manage_measurement_fields

app_name = "measures"

urlpatterns = [
    path(
        "measures/fields/",
        manage_measurement_fields,
        name="manage_measurement_fields",
    ),
]
