"""Modelos de `events`, partidos por tema.

Se reexportan aquí para que `from events.models import X` siga funcionando
igual que cuando todo vivía en un solo models.py.
"""

from .core import Event, EventCategory
from .registration import EventParticipant, EventTeamRegistration
from .staffing import (
    EventOrganization,
    EventStaffAssignment,
    EventStaffRole,
    Organization,
    StaffAccessLog,
    StaffMember,
)
from .judging import EventJudgingCriteria, EventResult, EventScore

__all__ = [
    "Event",
    "EventCategory",
    "EventTeamRegistration",
    "EventParticipant",
    "EventStaffRole",
    "EventStaffAssignment",
    "Organization",
    "EventOrganization",
    "StaffMember",
    "StaffAccessLog",
    "EventJudgingCriteria",
    "EventScore",
    "EventResult",
]
