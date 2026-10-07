from celery import shared_task

from events.services import ExternalStaffService


@shared_task(ignore_result=True)
def purge_external_staff_personal_data():
    """Borra foto y teléfono del staff externo 90 días después del evento."""
    return ExternalStaffService.purge_personal_data()
