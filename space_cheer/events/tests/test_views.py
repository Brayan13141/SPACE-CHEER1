import pytest
from django.urls import reverse

from accounts.models import Role, User
from events.models import Event


@pytest.fixture
def admin_user(db):
    role, _ = Role.objects.get_or_create(name='ADMIN')
    user = User.objects.create_user(
        username='admin_test', email='admin@test.com', password='pass123',
        profile_completed=True,
    )
    user.roles.add(role)
    return user


@pytest.fixture
def coach_user(db):
    role, _ = Role.objects.get_or_create(name='COACH', defaults={'is_coach_type': True})
    user = User.objects.create_user(
        username='coach_test', email='coach@test.com', password='pass123',
        profile_completed=True,
    )
    user.roles.add(role)
    return user


@pytest.fixture
def sample_event(db, admin_user):
    import datetime
    return Event.objects.create(
        name='Test Event',
        event_type='COMPETITION',
        status='DRAFT',
        organizer=admin_user,
        start_date=datetime.date(2026, 6, 1),
        end_date=datetime.date(2026, 6, 2),
    )


@pytest.mark.django_db
def test_event_list_requires_login(client):
    resp = client.get(reverse('events:event_list'))
    assert resp.status_code == 302
    assert '/accounts/' in resp.url


@pytest.mark.django_db
def test_event_list_ok_for_authenticated(client, admin_user):
    client.force_login(admin_user)
    resp = client.get(reverse('events:event_list'))
    assert resp.status_code == 200
    assert b'Competencias' in resp.content


@pytest.mark.django_db
def test_event_create_forbidden_for_coach(client, coach_user):
    client.force_login(coach_user)
    resp = client.get(reverse('events:event_create'))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_event_create_ok_for_admin(client, admin_user):
    client.force_login(admin_user)
    resp = client.get(reverse('events:event_create'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_event_detail_visible_to_all(client, coach_user, sample_event):
    client.force_login(coach_user)
    resp = client.get(reverse('events:event_detail', args=[sample_event.pk]))
    assert resp.status_code == 200
    assert b'Test Event' in resp.content


@pytest.mark.django_db
def test_event_create_post(client, admin_user):
    client.force_login(admin_user)
    resp = client.post(reverse('events:event_create'), {
        'name': 'New Event',
        'event_type': 'COMPETITION',
        'start_date': '2026-07-01',
        'end_date': '2026-07-02',
    })
    assert resp.status_code == 302
    assert Event.objects.filter(name='New Event').exists()


@pytest.mark.django_db
def test_team_register_requires_coach(client, admin_user, sample_event):
    """ADMIN sin equipo no puede registrar equipo."""
    client.force_login(admin_user)
    resp = client.get(reverse('events:team_register', args=[sample_event.pk]))
    assert resp.status_code == 302
