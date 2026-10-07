"""Servicios de `events`, partidos por tema.

Se reexportan aquí para que `from events.services import X` siga funcionando
igual que cuando todo vivía en un solo services.py.
"""

from .core import EventService
from .registration import EventRegistrationService
from .scoring import EventScoringService

__all__ = ["EventService", "EventRegistrationService", "EventScoringService"]
