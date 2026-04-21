import logging

from django.core.exceptions import ValidationError
from django.db import models, transaction

from .models import (
    BedAssignment,
    HospitalityPreference,
    Room,
    RoomAssignment,
    Stay,
)

logger = logging.getLogger(__name__)


class HospitalityService:

    @classmethod
    @transaction.atomic
    def create_stay(cls, *, event, user, created_by, event_participant=None, notes='') -> Stay:
        # Validates user doesn't already have a Stay for this event
        if Stay.objects.filter(event=event, user=user).exists():
            raise ValidationError(
                f"El usuario {user} ya tiene una estancia registrada para este evento."
            )
        stay = Stay(
            event=event,
            user=user,
            created_by=created_by,
            event_participant=event_participant,
            notes=notes,
            status=Stay.REQUESTED,
        )
        stay.save()
        logger.info("Stay created: user=%s event=%s created_by=%s", user, event, created_by)
        return stay

    @classmethod
    @transaction.atomic
    def confirm_stay(cls, *, stay, hotel, check_in_date, check_out_date, confirmed_by) -> Stay:
        # Validates stay.status must be REQUESTED
        if stay.status != Stay.REQUESTED:
            raise ValidationError(
                f"Solo se puede confirmar una estancia en estado REQUESTED. Estado actual: {stay.status}."
            )
        # Validates hotel.event must equal stay.event
        if hotel.event_id != stay.event_id:
            raise ValidationError("El hotel no pertenece al evento de esta estancia.")
        stay.status = Stay.CONFIRMED
        stay.hotel = hotel
        stay.check_in_date = check_in_date
        stay.check_out_date = check_out_date
        stay.save()
        logger.info("Stay confirmed: stay=%s hotel=%s confirmed_by=%s", stay.pk, hotel, confirmed_by)
        return stay

    @classmethod
    @transaction.atomic
    def cancel_stay(cls, *, stay, cancelled_by) -> Stay:
        # Validates stay.status not already CHECKED_IN or CHECKED_OUT
        if stay.status in (Stay.CHECKED_IN, Stay.CHECKED_OUT):
            raise ValidationError(
                f"No se puede cancelar una estancia con estado {stay.status}."
            )
        # Delete RoomAssignment and BedAssignment if they exist
        try:
            room_assignment = stay.room_assignment
            # BedAssignments cascade-delete from Stay, but delete explicitly for clarity
            stay.bed_assignments.all().delete()
            room_assignment.delete()
        except Stay.room_assignment.RelatedObjectDoesNotExist:
            pass
        stay.status = Stay.CANCELLED
        stay.save()
        logger.info("Stay cancelled: stay=%s cancelled_by=%s", stay.pk, cancelled_by)
        return stay

    @classmethod
    @transaction.atomic
    def check_in(cls, *, stay, checked_in_by) -> Stay:
        # Validates stay.status must be CONFIRMED
        if stay.status != Stay.CONFIRMED:
            raise ValidationError(
                f"Solo se puede hacer check-in de una estancia CONFIRMED. Estado actual: {stay.status}."
            )
        # Validates stay must have a RoomAssignment
        try:
            stay.room_assignment
        except Stay.room_assignment.RelatedObjectDoesNotExist:
            raise ValidationError("La estancia no tiene habitación asignada para hacer check-in.")
        # Validates stay must have at least one BedAssignment
        if not stay.bed_assignments.exists():
            raise ValidationError("La estancia no tiene cama asignada para hacer check-in.")
        stay.status = Stay.CHECKED_IN
        stay.save()
        logger.info("Stay checked in: stay=%s checked_in_by=%s", stay.pk, checked_in_by)
        return stay

    @classmethod
    @transaction.atomic
    def check_out(cls, *, stay, checked_out_by) -> Stay:
        # Validates stay.status must be CHECKED_IN
        if stay.status != Stay.CHECKED_IN:
            raise ValidationError(
                f"Solo se puede hacer check-out de una estancia CHECKED_IN. Estado actual: {stay.status}."
            )
        stay.status = Stay.CHECKED_OUT
        stay.save()
        logger.info("Stay checked out: stay=%s checked_out_by=%s", stay.pk, checked_out_by)
        return stay


class RoomAssignmentService:

    @classmethod
    @transaction.atomic
    def assign_room(cls, *, stay, room, assigned_by, notes='') -> RoomAssignment:
        # Validates stay.status is REQUESTED or CONFIRMED
        if stay.status not in (Stay.REQUESTED, Stay.CONFIRMED):
            raise ValidationError(
                f"Solo se puede asignar habitación a estancias REQUESTED o CONFIRMED. Estado: {stay.status}."
            )
        # Validates stay doesn't already have a room_assignment
        try:
            existing = stay.room_assignment
            if existing:
                raise ValidationError(
                    f"Esta estancia ya tiene asignada la habitación #{existing.room.room_number}."
                )
        except Stay.room_assignment.RelatedObjectDoesNotExist:
            pass
        # Validates capacity before hitting model clean() for a clear error message
        active_count = RoomAssignment.objects.filter(
            room=room
        ).exclude(
            stay__status=Stay.CANCELLED
        ).count()
        if active_count >= room.room_type.capacity:
            raise ValidationError(
                f"La habitación #{room.room_number} ha alcanzado su capacidad máxima "
                f"({room.room_type.capacity})."
            )
        assignment = RoomAssignment(
            stay=stay,
            room=room,
            assigned_by=assigned_by,
            notes=notes,
        )
        assignment.save()
        logger.info(
            "Room assigned: room=%s stay=%s assigned_by=%s",
            room, stay.pk, assigned_by,
        )
        return assignment

    @classmethod
    @transaction.atomic
    def assign_bed(cls, *, stay, bed, assigned_by, notes='') -> BedAssignment:
        # Validates bed.room matches stay's assigned room
        try:
            room_assignment = stay.room_assignment
        except Stay.room_assignment.RelatedObjectDoesNotExist:
            raise ValidationError("La estancia no tiene habitación asignada. Asigna una habitación primero.")
        if bed.room_id != room_assignment.room_id:
            raise ValidationError(
                "La cama no pertenece a la habitación asignada a esta estancia."
            )
        # Validates bed not already taken by another active stay
        already_assigned = BedAssignment.objects.filter(
            bed=bed
        ).exclude(
            stay__status=Stay.CANCELLED
        ).exists()
        if already_assigned:
            raise ValidationError("Esta cama ya está asignada a otro huésped.")
        assignment = BedAssignment(
            stay=stay,
            bed=bed,
            assigned_by=assigned_by,
            notes=notes,
        )
        assignment.save()
        logger.info(
            "Bed assigned: bed=%s stay=%s assigned_by=%s",
            bed, stay.pk, assigned_by,
        )
        return assignment

    @classmethod
    def get_available_rooms(cls, hotel, exclude_stay=None) -> models.QuerySet:
        # Returns rooms in hotel where active assignments < capacity, annotated with available_slots
        active_qs = RoomAssignment.objects.filter(
            room=models.OuterRef('pk')
        ).exclude(
            stay__status=Stay.CANCELLED
        )
        if exclude_stay is not None:
            active_qs = active_qs.exclude(stay=exclude_stay)

        # Annotate each room with its current active assignment count
        rooms = Room.objects.filter(
            hotel=hotel,
            is_available=True,
        ).annotate(
            current_assignments=models.Count(
                'assignments',
                filter=models.Q(
                    assignments__stay__status__in=[
                        Stay.REQUESTED,
                        Stay.CONFIRMED,
                        Stay.CHECKED_IN,
                        Stay.CHECKED_OUT,
                    ]
                ),
            )
        ).annotate(
            available_slots=models.F('room_type__capacity') - models.F('current_assignments')
        ).filter(
            available_slots__gt=0
        ).order_by('-available_slots')

        if exclude_stay is not None:
            # Re-annotate excluding the given stay from the count
            rooms = Room.objects.filter(
                hotel=hotel,
                is_available=True,
            ).annotate(
                current_assignments=models.Count(
                    'assignments',
                    filter=models.Q(
                        assignments__stay__status__in=[
                            Stay.REQUESTED,
                            Stay.CONFIRMED,
                            Stay.CHECKED_IN,
                            Stay.CHECKED_OUT,
                        ]
                    ) & ~models.Q(assignments__stay=exclude_stay),
                )
            ).annotate(
                available_slots=models.F('room_type__capacity') - models.F('current_assignments')
            ).filter(
                available_slots__gt=0
            ).order_by('-available_slots')

        return rooms

    @classmethod
    def get_room_occupancy(cls, room) -> dict:
        # Returns capacity, occupied, available, and active assignment objects for the room
        assignments = RoomAssignment.objects.filter(
            room=room
        ).exclude(
            stay__status=Stay.CANCELLED
        ).select_related('stay', 'stay__user')
        occupied = assignments.count()
        capacity = room.room_type.capacity
        return {
            'capacity': capacity,
            'occupied': occupied,
            'available': capacity - occupied,
            'assignments': assignments,
        }

    @classmethod
    @transaction.atomic
    def auto_assign_room(cls, *, stay, assigned_by) -> RoomAssignment:
        # Finds the best available room in stay.hotel using HospitalityPreference when present
        if stay.hotel is None:
            raise ValidationError("La estancia no tiene hotel asignado para la asignación automática.")

        # Load preference if it exists
        preference = HospitalityPreference.objects.filter(
            user=stay.user,
            event=stay.event,
        ).first()

        available_rooms = cls.get_available_rooms(stay.hotel)

        if not available_rooms.exists():
            raise ValidationError(
                f"No hay habitaciones disponibles en el hotel {stay.hotel.name}."
            )

        preferred_room_type = None
        roommate_user_ids = []

        if preference is not None:
            if preference.preferred_room_type_id:
                preferred_room_type = preference.preferred_room_type
            roommate_user_ids = list(
                preference.roommate_preferences.values_list('pk', flat=True)
            )

        best_room = None

        # Try to find a room where a preferred roommate is already assigned
        if roommate_user_ids:
            roommate_rooms = available_rooms.filter(
                assignments__stay__user_id__in=roommate_user_ids
            ).exclude(
                assignments__stay__status=Stay.CANCELLED
            ).distinct()
            # Narrow to preferred type first if set
            if preferred_room_type is not None:
                typed_roommate_rooms = roommate_rooms.filter(room_type=preferred_room_type)
                if typed_roommate_rooms.exists():
                    best_room = typed_roommate_rooms.first()
            if best_room is None and roommate_rooms.exists():
                best_room = roommate_rooms.first()

        # Fall back to preferred room type if no roommate room found
        if best_room is None and preferred_room_type is not None:
            typed_rooms = available_rooms.filter(room_type=preferred_room_type)
            if typed_rooms.exists():
                best_room = typed_rooms.first()

        # Fall back to any available room
        if best_room is None:
            best_room = available_rooms.first()

        logger.info(
            "Auto-assigning room: stay=%s room=%s assigned_by=%s",
            stay.pk, best_room, assigned_by,
        )
        return cls.assign_room(stay=stay, room=best_room, assigned_by=assigned_by)
