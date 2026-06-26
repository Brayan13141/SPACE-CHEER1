"""
Seed script: fixes CURPs + creates events/stays/orders/tasks for test users.
Run from repo root: python seed_test_data.py
"""
import os, sys, django
from datetime import date, timedelta

sys.path.insert(0, "C:/Users/Lenovo/Documents/SPACE-CHEER/space_cheer")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "space_cheer.settings")
django.setup()

from accounts.models import User
from hospitality.models import Hotel, Room, Stay, RoomAssignment
from events.models import Event, EventParticipant, EventTeamRegistration
from orders.models import Order
from production.models import ProductionRole, OperarioRoleAssignment, ProductionJob, ProductionTask, ProductionStage
from teams.models import Team

admin = User.objects.get(pk=1)
event  = Event.objects.get(pk=8)   # Grand Prix Espacial 2026
hotel1 = Hotel.objects.get(pk=1)   # NUEVO
hotel2 = Hotel.objects.get(pk=2)   # ewvjcnew
room_suite  = Room.objects.get(pk=2)   # hotel1
room_cuad   = Room.objects.get(pk=3)   # hotel1
room_indiv  = Room.objects.get(pk=1)   # hotel2

today     = date.today()
checkin   = today + timedelta(days=30)
checkout  = today + timedelta(days=33)

users = {
    "atleta_test":    (167, "ATAL900101HDFLLR04", "ATHLETE",  hotel1, room_cuad),
    "guardian_test":  (170, "GULL850101MDFRRR06", "GUARDIAN", hotel1, room_suite),
    "juez_test":      (169, "JUEZ900101HDFLLR08", "GUEST",    hotel2, room_indiv),
    "headcoach_test": ( 51, None,                 "COACH",    hotel1, room_cuad),
    "coach_test":     (164, None,                 "COACH",    hotel1, room_suite),
}

print("=== 1. CURPs ===")
for username, (pk, curp, _, _, _) in users.items():
    if curp:
        User.objects.filter(pk=pk).update(curp=curp)
        print(f"  {username} → curp={curp}")

print("\n=== 2. EventParticipants ===")
for username, (pk, _, ep_role, _, _) in users.items():
    u = User.objects.get(pk=pk)
    ep, created = EventParticipant.objects.get_or_create(
        event=event, user=u,
        defaults={"role": ep_role, "status": "CONFIRMED"},
    )
    print(f"  {'created' if created else 'exists'} EP {username} role={ep_role}")

print("\n=== 3. Stays ===")
stays = {}
for username, (pk, _, _, hotel, room) in users.items():
    u = User.objects.get(pk=pk)
    stay, created = Stay.objects.get_or_create(
        event=event, user=u,
        defaults={
            "hotel": hotel,
            "check_in_date": checkin,
            "check_out_date": checkout,
            "status": "CONFIRMED",
            "notes": "Hospedaje de prueba — datos de muestra",
            "created_by": admin,
        },
    )
    stays[username] = stay
    print(f"  {'created' if created else 'exists'} Stay {username} hotel={hotel.name} status={stay.status}")

    # RoomAssignment
    if created:
        try:
            RA, ra_created = RoomAssignment.objects.get_or_create(
                stay=stay, room=room,
                defaults={"assigned_by": admin, "notes": "Asignación de prueba"},
            )
            print(f"    {'created' if ra_created else 'exists'} RoomAssignment room={room.room_number}")
        except Exception as e:
            print(f"    skip RoomAssignment ({e})")

print("\n=== 4. Order for atleta_test ===")
atleta = User.objects.get(pk=167)
if not Order.objects.filter(owner_user=atleta).exists():
    order = Order.objects.create(
        order_type="PERSONAL",
        owner_user=atleta,
        created_by=admin,
        status="DRAFT",
    )
    print(f"  Created Order pk={order.pk} status={order.status}")
else:
    print(f"  Order already exists for atleta_test")

print("\n=== 5. OperarioRoleAssignment for operario1 ===")
op1 = User.objects.get(pk=165)
for role_name in ("Cristalero", "Logística"):
    pr = ProductionRole.objects.get(name=role_name)
    ora, created = OperarioRoleAssignment.objects.get_or_create(
        user=op1, role=pr,
        defaults={"assigned_by": admin},
    )
    print(f"  {'created' if created else 'exists'} ORA operario1 → {role_name}")

print("\n=== 6. Existing ProductionTasks for operario1 ===")
existing_tasks = ProductionTask.objects.filter(assigned_to=op1)
print(f"  operario1 already has {existing_tasks.count()} task(s):")
for t in existing_tasks:
    print(f"    pk={t.pk} status={t.status} stage={getattr(t.stage,'name','?')}")

print("\nDone. All test data seeded.")
