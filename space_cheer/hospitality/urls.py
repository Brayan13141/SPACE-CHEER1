from django.urls import path

import hospitality.views.admin_views as admin_views
import hospitality.views.participant_views as participant_views

app_name = 'hospitality'

urlpatterns = [
    # Index — entry point sin event_pk
    path('', admin_views.hospitality_index, name='index'),
    # Admin — room features (catálogo global)
    path('features/', admin_views.room_feature_list, name='room_feature_list'),
    path('features/create/', admin_views.room_feature_create, name='room_feature_create'),
    path('features/<int:pk>/edit/', admin_views.room_feature_edit, name='room_feature_edit'),
    path('features/<int:pk>/delete/', admin_views.room_feature_delete, name='room_feature_delete'),
    # Admin — hotels
    path('event/<int:event_pk>/hotels/', admin_views.hotel_list, name='hotel_list'),
    path('event/<int:event_pk>/hotels/create/', admin_views.hotel_create, name='hotel_create'),
    path('event/<int:event_pk>/hotels/<int:pk>/', admin_views.hotel_detail, name='hotel_detail'),
    path('event/<int:event_pk>/hotels/<int:pk>/edit/', admin_views.hotel_edit, name='hotel_edit'),
    # Admin — room types
    path('event/<int:event_pk>/hotels/<int:hotel_pk>/room-types/presets/', admin_views.room_type_preset_apply, name='room_type_preset_apply'),
    path('event/<int:event_pk>/hotels/<int:hotel_pk>/room-types/create/', admin_views.room_type_create, name='room_type_create'),
    path('event/<int:event_pk>/hotels/<int:hotel_pk>/room-types/<int:pk>/edit/', admin_views.room_type_edit, name='room_type_edit'),
    # Admin — rooms
    path('event/<int:event_pk>/hotels/<int:hotel_pk>/rooms/create/', admin_views.room_create, name='room_create'),
    path('event/<int:event_pk>/hotels/<int:hotel_pk>/rooms/<int:pk>/edit/', admin_views.room_edit, name='room_edit'),
    # Admin — beds
    path('event/<int:event_pk>/hotels/<int:hotel_pk>/rooms/<int:room_pk>/beds/create/', admin_views.bed_create, name='bed_create'),
    # Admin — stays
    path('event/<int:event_pk>/stays/', admin_views.stay_list, name='stay_list'),
    path('event/<int:event_pk>/stays/create/', admin_views.stay_create, name='stay_create'),
    path('event/<int:event_pk>/stays/<int:pk>/', admin_views.stay_detail, name='stay_detail'),
    path('event/<int:event_pk>/stays/<int:pk>/confirm/', admin_views.stay_confirm, name='stay_confirm'),
    path('event/<int:event_pk>/stays/<int:pk>/cancel/', admin_views.stay_cancel, name='stay_cancel'),
    path('event/<int:event_pk>/stays/<int:pk>/checkin/', admin_views.stay_checkin, name='stay_checkin'),
    path('event/<int:event_pk>/stays/<int:pk>/checkout/', admin_views.stay_checkout, name='stay_checkout'),
    # Admin — assignments
    path('event/<int:event_pk>/stays/<int:stay_pk>/assign-room/', admin_views.room_assign, name='room_assign'),
    path('event/<int:event_pk>/stays/<int:stay_pk>/auto-assign-room/', admin_views.room_auto_assign, name='room_auto_assign'),
    path('event/<int:event_pk>/stays/<int:stay_pk>/assign-bed/', admin_views.bed_assign, name='bed_assign'),
    # Participant
    path('event/<int:event_pk>/my-stay/', participant_views.my_stay, name='my_stay'),
    path('event/<int:event_pk>/preferences/', participant_views.preference_form, name='preference_form'),
]
