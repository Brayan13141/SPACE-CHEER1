import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from events.models import Event
from hospitality.forms import (
    BedAssignForm,
    BedForm,
    HotelForm,
    RoomAssignForm,
    RoomFeatureForm,
    RoomForm,
    RoomTypeForm,
    StayConfirmForm,
    StayCreateForm,
)
from hospitality.models import Bed, Hotel, Room, RoomAssignment, RoomFeature, RoomType, Stay
from hospitality.services import HospitalityService, RoomAssignmentService

logger = logging.getLogger(__name__)


# ── Index ─────────────────────────────────────────────────────────────────────

@login_required
def hospitality_index(request):
    is_admin = request.user.roles.filter(name='ADMIN').exists() or request.user.is_superuser

    my_stays = (
        Stay.objects.filter(user=request.user)
        .select_related('event', 'hotel', 'room_assignment__room__room_type')
        .order_by('-event__start_date')
    )

    if is_admin:
        events = (
            Event.objects.annotate(
                hotel_count=Count('hotels', distinct=True),
                stay_count=Count('stays', distinct=True),
            )
            .filter(hotel_count__gt=0)
            .order_by('-start_date')
        )
        events_no_hotels = (
            Event.objects.annotate(hotel_count=Count('hotels', distinct=True))
            .filter(hotel_count=0)
            .order_by('-start_date')[:10]
        )
        return render(request, 'hospitality/index.html', {
            'events': events,
            'events_no_hotels': events_no_hotels,
            'my_stays': my_stays,
            'is_admin': True,
        })

    return render(request, 'hospitality/index.html', {
        'stays': my_stays,
        'is_admin': False,
    })


# ── Hotels ────────────────────────────────────────────────────────────────────

@role_required('ADMIN')
def hotel_list(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk)
    hotels = Hotel.objects.filter(event=event).prefetch_related('room_types', 'rooms')
    return render(request, 'hospitality/hotel_list.html', {
        'event': event,
        'hotels': hotels,
    })


@role_required('ADMIN')
def hotel_create(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk)
    form = HotelForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        hotel = form.save(commit=False)
        hotel.event = event
        hotel.save()
        messages.success(request, f'Hotel "{hotel.name}" creado.')
        return redirect('hospitality:hotel_detail', event_pk=event.pk, pk=hotel.pk)
    return render(request, 'hospitality/hotel_form.html', {
        'form': form, 'event': event, 'is_edit': False,
    })


@role_required('ADMIN')
def hotel_edit(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk)
    hotel = get_object_or_404(Hotel, pk=pk, event=event)
    form = HotelForm(request.POST or None, request.FILES or None, instance=hotel)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Hotel "{hotel.name}" actualizado.')
        return redirect('hospitality:hotel_detail', event_pk=event.pk, pk=hotel.pk)
    return render(request, 'hospitality/hotel_form.html', {
        'form': form, 'event': event, 'hotel': hotel, 'is_edit': True,
    })


@role_required('ADMIN')
def hotel_detail(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk)
    hotel = get_object_or_404(Hotel, pk=pk, event=event)
    room_types = hotel.room_types.prefetch_related('features', 'rooms').all()
    rooms = hotel.rooms.select_related('room_type').all()
    return render(request, 'hospitality/hotel_detail.html', {
        'event': event,
        'hotel': hotel,
        'room_types': room_types,
        'rooms': rooms,
    })


# ── RoomTypes ─────────────────────────────────────────────────────────────────

@role_required('ADMIN')
def room_type_create(request, event_pk, hotel_pk):
    event = get_object_or_404(Event, pk=event_pk)
    hotel = get_object_or_404(Hotel, pk=hotel_pk, event=event)
    form = RoomTypeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        rt = form.save(commit=False)
        rt.hotel = hotel
        rt.save()
        form.save_m2m()
        messages.success(request, f'Tipo de habitación "{rt.name}" creado.')
        return redirect('hospitality:hotel_detail', event_pk=event.pk, pk=hotel.pk)
    return render(request, 'hospitality/room_type_form.html', {
        'form': form, 'event': event, 'hotel': hotel, 'is_edit': False,
    })


@role_required('ADMIN')
def room_type_edit(request, event_pk, hotel_pk, pk):
    event = get_object_or_404(Event, pk=event_pk)
    hotel = get_object_or_404(Hotel, pk=hotel_pk, event=event)
    rt = get_object_or_404(RoomType, pk=pk, hotel=hotel)
    form = RoomTypeForm(request.POST or None, instance=rt)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Tipo "{rt.name}" actualizado.')
        return redirect('hospitality:hotel_detail', event_pk=event.pk, pk=hotel.pk)
    return render(request, 'hospitality/room_type_form.html', {
        'form': form, 'event': event, 'hotel': hotel, 'room_type': rt, 'is_edit': True,
    })


# ── Rooms ─────────────────────────────────────────────────────────────────────

@role_required('ADMIN')
def room_create(request, event_pk, hotel_pk):
    event = get_object_or_404(Event, pk=event_pk)
    hotel = get_object_or_404(Hotel, pk=hotel_pk, event=event)
    form = RoomForm(hotel, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            room = form.save(commit=False)
            room.hotel = hotel
            room.save()
            messages.success(request, f'Habitación #{room.room_number} creada.')
            return redirect('hospitality:hotel_detail', event_pk=event.pk, pk=hotel.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    return render(request, 'hospitality/room_form.html', {
        'form': form, 'event': event, 'hotel': hotel, 'is_edit': False,
    })


@role_required('ADMIN')
def room_edit(request, event_pk, hotel_pk, pk):
    event = get_object_or_404(Event, pk=event_pk)
    hotel = get_object_or_404(Hotel, pk=hotel_pk, event=event)
    room = get_object_or_404(Room, pk=pk, hotel=hotel)
    form = RoomForm(hotel, request.POST or None, instance=room)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, f'Habitación #{room.room_number} actualizada.')
            return redirect('hospitality:hotel_detail', event_pk=event.pk, pk=hotel.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    return render(request, 'hospitality/room_form.html', {
        'form': form, 'event': event, 'hotel': hotel, 'room': room, 'is_edit': True,
    })


# ── Beds ──────────────────────────────────────────────────────────────────────

@role_required('ADMIN')
def bed_create(request, event_pk, hotel_pk, room_pk):
    event = get_object_or_404(Event, pk=event_pk)
    hotel = get_object_or_404(Hotel, pk=hotel_pk, event=event)
    room = get_object_or_404(Room, pk=room_pk, hotel=hotel)
    form = BedForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        bed = form.save(commit=False)
        bed.room = room
        bed.save()
        messages.success(request, 'Cama agregada.')
        return redirect('hospitality:hotel_detail', event_pk=event.pk, pk=hotel.pk)
    return render(request, 'hospitality/bed_form.html', {
        'form': form, 'event': event, 'hotel': hotel, 'room': room,
    })


# ── Stays ─────────────────────────────────────────────────────────────────────

@role_required('ADMIN')
def stay_list(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk)
    stays = (
        Stay.objects.filter(event=event)
        .select_related('user', 'hotel', 'room_assignment__room__room_type')
        .order_by('status', 'user__first_name')
    )
    status_filter = request.GET.get('status', '')
    if status_filter:
        stays = stays.filter(status=status_filter)
    return render(request, 'hospitality/stay_list.html', {
        'event': event,
        'stays': stays,
        'status_choices': Stay.STATUS_CHOICES,
        'status_filter': status_filter,
    })


@role_required('ADMIN')
def stay_create(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk)
    form = StayCreateForm(event, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            stay = HospitalityService.create_stay(
                event=event,
                user=form.cleaned_data['user'],
                created_by=request.user,
                notes=form.cleaned_data.get('notes', ''),
            )
            messages.success(request, f'Estancia creada para {stay.user}.')
            return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    return render(request, 'hospitality/stay_create.html', {
        'form': form, 'event': event,
    })


@role_required('ADMIN')
def stay_detail(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk)
    stay = get_object_or_404(
        Stay.objects.select_related(
            'user', 'hotel', 'room_assignment__room__room_type',
            'created_by',
        ).prefetch_related('bed_assignments__bed'),
        pk=pk, event=event,
    )
    try:
        room_assignment = stay.room_assignment
    except Stay.room_assignment.RelatedObjectDoesNotExist:
        room_assignment = None

    bed_assignments = stay.bed_assignments.select_related('bed__room').all()

    return render(request, 'hospitality/stay_detail.html', {
        'event': event,
        'stay': stay,
        'room_assignment': room_assignment,
        'bed_assignments': bed_assignments,
    })


@role_required('ADMIN')
def stay_confirm(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk)
    stay = get_object_or_404(Stay, pk=pk, event=event)
    form = StayConfirmForm(event, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            HospitalityService.confirm_stay(
                stay=stay,
                hotel=form.cleaned_data['hotel'],
                check_in_date=form.cleaned_data['check_in_date'],
                check_out_date=form.cleaned_data['check_out_date'],
                confirmed_by=request.user,
            )
            messages.success(request, 'Estancia confirmada.')
            return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    return render(request, 'hospitality/stay_confirm.html', {
        'form': form, 'event': event, 'stay': stay,
    })


@role_required('ADMIN')
def stay_cancel(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk)
    stay = get_object_or_404(Stay, pk=pk, event=event)
    if request.method == 'POST':
        try:
            HospitalityService.cancel_stay(stay=stay, cancelled_by=request.user)
            messages.success(request, 'Estancia cancelada.')
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
        return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)
    return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)


@role_required('ADMIN')
def stay_checkin(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk)
    stay = get_object_or_404(Stay, pk=pk, event=event)
    if request.method == 'POST':
        try:
            HospitalityService.check_in(stay=stay, checked_in_by=request.user)
            messages.success(request, 'Check-in realizado.')
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
        return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)
    return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)


@role_required('ADMIN')
def stay_checkout(request, event_pk, pk):
    event = get_object_or_404(Event, pk=event_pk)
    stay = get_object_or_404(Stay, pk=pk, event=event)
    if request.method == 'POST':
        try:
            HospitalityService.check_out(stay=stay, checked_out_by=request.user)
            messages.success(request, 'Check-out realizado.')
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
        return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)
    return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)


# ── Room / Bed Assignment ─────────────────────────────────────────────────────

@role_required('ADMIN')
def room_assign(request, event_pk, stay_pk):
    event = get_object_or_404(Event, pk=event_pk)
    stay = get_object_or_404(Stay, pk=stay_pk, event=event)
    if not stay.hotel:
        messages.error(request, 'Confirma la estancia y asigna un hotel primero.')
        return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)
    form = RoomAssignForm(stay.hotel, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            RoomAssignmentService.assign_room(
                stay=stay,
                room=form.cleaned_data['room'],
                assigned_by=request.user,
                notes=form.cleaned_data.get('notes', ''),
            )
            messages.success(request, 'Habitación asignada.')
            return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    return render(request, 'hospitality/room_assign.html', {
        'form': form, 'event': event, 'stay': stay,
    })


@role_required('ADMIN')
def room_auto_assign(request, event_pk, stay_pk):
    event = get_object_or_404(Event, pk=event_pk)
    stay = get_object_or_404(Stay, pk=stay_pk, event=event)
    if request.method == 'POST':
        try:
            RoomAssignmentService.auto_assign_room(stay=stay, assigned_by=request.user)
            messages.success(request, 'Habitación asignada automáticamente.')
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
        return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)
    return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)


@role_required('ADMIN')
def bed_assign(request, event_pk, stay_pk):
    event = get_object_or_404(Event, pk=event_pk)
    stay = get_object_or_404(Stay, pk=stay_pk, event=event)
    try:
        room_assignment = stay.room_assignment
    except Stay.room_assignment.RelatedObjectDoesNotExist:
        messages.error(request, 'Asigna una habitación antes de asignar una cama.')
        return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)
    form = BedAssignForm(room_assignment.room, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            RoomAssignmentService.assign_bed(
                stay=stay,
                bed=form.cleaned_data['bed'],
                assigned_by=request.user,
                notes=form.cleaned_data.get('notes', ''),
            )
            messages.success(request, 'Cama asignada.')
            return redirect('hospitality:stay_detail', event_pk=event.pk, pk=stay.pk)
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))
    return render(request, 'hospitality/bed_assign.html', {
        'form': form, 'event': event, 'stay': stay,
        'room': room_assignment.room,
    })


# ── RoomType presets ──────────────────────────────────────────────────────────

ROOM_TYPE_PRESETS = [
    {"name": "Individual",          "capacity": 1},
    {"name": "Doble",               "capacity": 2},
    {"name": "Triple",              "capacity": 3},
    {"name": "Cuádruple",           "capacity": 4},
    {"name": "Queen",               "capacity": 2},
    {"name": "King",                "capacity": 2},
    {"name": "Suite Junior",        "capacity": 2},
    {"name": "Suite",               "capacity": 2},
    {"name": "Suite Familiar",      "capacity": 4},
    {"name": "Suite Presidencial",  "capacity": 4},
]


@role_required('ADMIN')
def room_type_preset_apply(request, event_pk, hotel_pk):
    """Crea los tipos de habitación estándar para un hotel si no existen."""
    event = get_object_or_404(Event, pk=event_pk)
    hotel = get_object_or_404(Hotel, pk=hotel_pk, event=event)
    if request.method == 'POST':
        created = 0
        for preset in ROOM_TYPE_PRESETS:
            _, was_created = RoomType.objects.get_or_create(
                hotel=hotel,
                name=preset['name'],
                defaults={'capacity': preset['capacity']},
            )
            if was_created:
                created += 1
        if created:
            messages.success(request, f'{created} tipo(s) de habitación creados.')
        else:
            messages.info(request, 'Todos los tipos estándar ya existían.')
    return redirect('hospitality:hotel_detail', event_pk=event.pk, pk=hotel.pk)


# ── RoomFeature (catálogo global) ─────────────────────────────────────────────

@role_required('ADMIN')
def room_feature_list(request):
    features = RoomFeature.objects.order_by('name')
    return render(request, 'hospitality/room_feature_list.html', {
        'features': features,
    })


@role_required('ADMIN')
def room_feature_create(request):
    form = RoomFeatureForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        feature = form.save()
        messages.success(request, f'Característica "{feature.name}" creada.')
        return redirect('hospitality:room_feature_list')
    return render(request, 'hospitality/room_feature_form.html', {
        'form': form, 'is_edit': False,
    })


@role_required('ADMIN')
def room_feature_edit(request, pk):
    feature = get_object_or_404(RoomFeature, pk=pk)
    form = RoomFeatureForm(request.POST or None, instance=feature)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Característica "{feature.name}" actualizada.')
        return redirect('hospitality:room_feature_list')
    return render(request, 'hospitality/room_feature_form.html', {
        'form': form, 'feature': feature, 'is_edit': True,
    })


@role_required('ADMIN')
def room_feature_delete(request, pk):
    feature = get_object_or_404(RoomFeature, pk=pk)
    if request.method == 'POST':
        name = feature.name
        feature.delete()
        messages.success(request, f'Característica "{name}" eliminada.')
        return redirect('hospitality:room_feature_list')
    return redirect('hospitality:room_feature_list')
