import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from events.models import Event
from hospitality.forms import HospitalityPreferenceForm
from hospitality.models import HospitalityPreference, Stay

logger = logging.getLogger(__name__)


@login_required
def my_stay(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk)
    stay = Stay.objects.filter(event=event, user=request.user).select_related(
        'hotel', 'room_assignment__room__room_type',
    ).prefetch_related('bed_assignments__bed').first()
    preference = HospitalityPreference.objects.filter(
        event=event, user=request.user
    ).first()
    return render(request, 'hospitality/my_stay.html', {
        'event': event,
        'stay': stay,
        'preference': preference,
    })


@login_required
def preference_form(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk)
    instance = HospitalityPreference.objects.filter(
        event=event, user=request.user
    ).first()
    form = HospitalityPreferenceForm(
        event, request.user,
        request.POST or None,
        instance=instance,
    )
    if request.method == 'POST' and form.is_valid():
        pref = form.save(commit=False)
        pref.event = event
        pref.user = request.user
        pref.save()
        form.save_m2m()
        messages.success(request, 'Preferencias guardadas.')
        return redirect('hospitality:my_stay', event_pk=event.pk)
    return render(request, 'hospitality/preference_form.html', {
        'form': form, 'event': event, 'is_edit': instance is not None,
    })
