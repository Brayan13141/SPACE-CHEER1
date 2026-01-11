from django.urls import path
from .views import manage_measurement_fields

urlpatterns = [
    path(
        "measures/fields/",
        manage_measurement_fields,
        name="manage_measurement_fields",
    ),
]
