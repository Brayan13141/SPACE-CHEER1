from .public_views import event_list, event_detail  # noqa: F401
from .admin_views import (  # noqa: F401
    event_create,
    event_edit,
    event_status,
    registrations_list,
    registration_accept,
    registration_reject,
    staff_manage,
    criteria_manage,
    score_entry,
    results_manage,
)
from .coach_views import team_register, my_registrations  # noqa: F401
