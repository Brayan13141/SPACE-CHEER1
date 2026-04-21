from django.urls import path

import events.views.admin_views as admin_views
import events.views.coach_views as coach_views
import events.views.judge_views as judge_views
import events.views.public_views as public_views

app_name = 'events'

urlpatterns = [
    # Public
    path('', public_views.event_list, name='event_list'),
    path('my-registrations/', coach_views.my_registrations, name='my_registrations'),
    path('<int:pk>/', public_views.event_detail, name='event_detail'),
    # Admin — event CRUD
    path('create/', admin_views.event_create, name='event_create'),
    path('<int:pk>/edit/', admin_views.event_edit, name='event_edit'),
    path('<int:pk>/status/', admin_views.event_status, name='event_status'),
    # Admin — management
    path('<int:pk>/registrations/', admin_views.registrations_list, name='registrations_list'),
    path('<int:pk>/registrations/<int:reg_pk>/accept/', admin_views.registration_accept, name='registration_accept'),
    path('<int:pk>/registrations/<int:reg_pk>/reject/', admin_views.registration_reject, name='registration_reject'),
    path('<int:pk>/staff/', admin_views.staff_manage, name='staff_manage'),
    path('<int:pk>/criteria/', admin_views.criteria_manage, name='criteria_manage'),
    path('<int:pk>/scores/', admin_views.score_entry, name='score_entry'),
    path('<int:pk>/results/', admin_views.results_manage, name='results_manage'),
    # Coach
    path('<int:pk>/register/', coach_views.team_register, name='team_register'),
    path('registrations/<int:reg_pk>/withdraw/', coach_views.registration_withdraw, name='registration_withdraw'),
    # Juez — panel de evaluación en tiempo real
    path('<int:pk>/judge/', judge_views.judge_panel, name='judge_panel'),
    path('<int:pk>/judge/score/', judge_views.judge_score_submit, name='judge_score_submit'),
    path('<int:pk>/judge/leaderboard/', judge_views.judge_leaderboard_api, name='judge_leaderboard_api'),
]
