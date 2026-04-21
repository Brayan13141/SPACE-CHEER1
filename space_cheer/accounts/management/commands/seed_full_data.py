# accounts/management/commands/seed_full_data.py
"""
Pobla la BD con equipos, coaches, atletas con mediciones y nuevos eventos.

Uso:
    python manage.py seed_full_data
    python manage.py seed_full_data --reset

Prerequisito: seed_roles y seed_products deben haberse ejecutado antes.
Idempotente. Seguro de correr múltiples veces.

Orden:
    1. Roles (verifica existencia)
    2. Usuarios — 3 headcoaches, 6 coaches, 24 atletas
    3. Equipos — Comets, Supernovas, Meteors con membresías
    4. Perfiles de atleta + mediciones
    5. Eventos — Grand Prix Espacial 2026 + Copa Galaxia 2026
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()

# ─── Identificadores ──────────────────────────────────────────────────────────

TEST_EMAILS_FULL = [
    # Headcoaches
    "hc.comets@test.com",
    "hc.supernovas@test.com",
    "hc.meteors@test.com",
    # Coaches
    "coach.comets1@test.com", "coach.comets2@test.com",
    "coach.supernovas1@test.com", "coach.supernovas2@test.com",
    "coach.meteors1@test.com", "coach.meteors2@test.com",
    # Atletas — Comets
    "atleta.comets1@test.com", "atleta.comets2@test.com",
    "atleta.comets3@test.com", "atleta.comets4@test.com",
    "atleta.comets5@test.com", "atleta.comets6@test.com",
    "atleta.comets7@test.com", "atleta.comets8@test.com",
    # Atletas — Supernovas
    "atleta.supernovas1@test.com", "atleta.supernovas2@test.com",
    "atleta.supernovas3@test.com", "atleta.supernovas4@test.com",
    "atleta.supernovas5@test.com", "atleta.supernovas6@test.com",
    "atleta.supernovas7@test.com", "atleta.supernovas8@test.com",
    # Atletas — Meteors
    "atleta.meteors1@test.com", "atleta.meteors2@test.com",
    "atleta.meteors3@test.com", "atleta.meteors4@test.com",
    "atleta.meteors5@test.com", "atleta.meteors6@test.com",
    "atleta.meteors7@test.com", "atleta.meteors8@test.com",
]

EVENT_NAMES = [
    "Grand Prix Espacial 2026 — SEED",
    "Copa Galaxia 2026 — SEED",
]

# ─── Datos de usuarios ────────────────────────────────────────────────────────

USERS_DATA = [
    # Headcoaches
    {"email": "hc.comets@test.com",      "username": "hc_comets",      "first_name": "Diego",    "last_name": "Orión",      "role": "HEADCOACH", "key": "hc_comets"},
    {"email": "hc.supernovas@test.com",  "username": "hc_supernovas",  "first_name": "Mariana",  "last_name": "Polaris",    "role": "HEADCOACH", "key": "hc_supernovas"},
    {"email": "hc.meteors@test.com",     "username": "hc_meteors",     "first_name": "Rodrigo",  "last_name": "Altair",     "role": "HEADCOACH", "key": "hc_meteors"},
    # Coaches Comets
    {"email": "coach.comets1@test.com",  "username": "coach_comets1",  "first_name": "Laura",    "last_name": "Sirius",     "role": "COACH",     "key": "coach_comets1"},
    {"email": "coach.comets2@test.com",  "username": "coach_comets2",  "first_name": "Jorge",    "last_name": "Rigel",      "role": "COACH",     "key": "coach_comets2"},
    # Coaches Supernovas
    {"email": "coach.supernovas1@test.com", "username": "coach_supernovas1", "first_name": "Paola",  "last_name": "Capella",  "role": "COACH", "key": "coach_supernovas1"},
    {"email": "coach.supernovas2@test.com", "username": "coach_supernovas2", "first_name": "Héctor", "last_name": "Deneb",    "role": "COACH", "key": "coach_supernovas2"},
    # Coaches Meteors
    {"email": "coach.meteors1@test.com", "username": "coach_meteors1", "first_name": "Natalia", "last_name": "Vega",       "role": "COACH",     "key": "coach_meteors1"},
    {"email": "coach.meteors2@test.com", "username": "coach_meteors2", "first_name": "Carlos",  "last_name": "Arcturus",   "role": "COACH",     "key": "coach_meteors2"},
    # Atletas Comets
    {"email": "atleta.comets1@test.com", "username": "atleta_comets1", "first_name": "Sofía",    "last_name": "Cruz",       "role": "ATHLETE",   "key": "atleta_comets1"},
    {"email": "atleta.comets2@test.com", "username": "atleta_comets2", "first_name": "Valeria",  "last_name": "Torres",     "role": "ATHLETE",   "key": "atleta_comets2"},
    {"email": "atleta.comets3@test.com", "username": "atleta_comets3", "first_name": "Camila",   "last_name": "Ramírez",    "role": "ATHLETE",   "key": "atleta_comets3"},
    {"email": "atleta.comets4@test.com", "username": "atleta_comets4", "first_name": "Isabella", "last_name": "Flores",     "role": "ATHLETE",   "key": "atleta_comets4"},
    {"email": "atleta.comets5@test.com", "username": "atleta_comets5", "first_name": "Daniela",  "last_name": "Reyes",      "role": "ATHLETE",   "key": "atleta_comets5"},
    {"email": "atleta.comets6@test.com", "username": "atleta_comets6", "first_name": "Fernanda", "last_name": "Morales",    "role": "ATHLETE",   "key": "atleta_comets6"},
    {"email": "atleta.comets7@test.com", "username": "atleta_comets7", "first_name": "Lucía",    "last_name": "Jiménez",    "role": "ATHLETE",   "key": "atleta_comets7"},
    {"email": "atleta.comets8@test.com", "username": "atleta_comets8", "first_name": "Andrea",   "last_name": "López",      "role": "ATHLETE",   "key": "atleta_comets8"},
    # Atletas Supernovas
    {"email": "atleta.supernovas1@test.com", "username": "atleta_supernovas1", "first_name": "Regina",    "last_name": "Mendoza",  "role": "ATHLETE", "key": "atleta_supernovas1"},
    {"email": "atleta.supernovas2@test.com", "username": "atleta_supernovas2", "first_name": "Ximena",    "last_name": "Castro",   "role": "ATHLETE", "key": "atleta_supernovas2"},
    {"email": "atleta.supernovas3@test.com", "username": "atleta_supernovas3", "first_name": "Renata",    "last_name": "Guzmán",   "role": "ATHLETE", "key": "atleta_supernovas3"},
    {"email": "atleta.supernovas4@test.com", "username": "atleta_supernovas4", "first_name": "Alejandra", "last_name": "Herrera",  "role": "ATHLETE", "key": "atleta_supernovas4"},
    {"email": "atleta.supernovas5@test.com", "username": "atleta_supernovas5", "first_name": "Mariana",   "last_name": "Ríos",     "role": "ATHLETE", "key": "atleta_supernovas5"},
    {"email": "atleta.supernovas6@test.com", "username": "atleta_supernovas6", "first_name": "Karla",     "last_name": "Ortega",   "role": "ATHLETE", "key": "atleta_supernovas6"},
    {"email": "atleta.supernovas7@test.com", "username": "atleta_supernovas7", "first_name": "Diana",     "last_name": "Vargas",   "role": "ATHLETE", "key": "atleta_supernovas7"},
    {"email": "atleta.supernovas8@test.com", "username": "atleta_supernovas8", "first_name": "Brenda",    "last_name": "Peña",     "role": "ATHLETE", "key": "atleta_supernovas8"},
    # Atletas Meteors
    {"email": "atleta.meteors1@test.com", "username": "atleta_meteors1", "first_name": "Natalia",   "last_name": "Salinas",  "role": "ATHLETE", "key": "atleta_meteors1"},
    {"email": "atleta.meteors2@test.com", "username": "atleta_meteors2", "first_name": "Paulina",   "last_name": "Aguilar",  "role": "ATHLETE", "key": "atleta_meteors2"},
    {"email": "atleta.meteors3@test.com", "username": "atleta_meteors3", "first_name": "Stephanie", "last_name": "Romero",   "role": "ATHLETE", "key": "atleta_meteors3"},
    {"email": "atleta.meteors4@test.com", "username": "atleta_meteors4", "first_name": "Mónica",    "last_name": "Sánchez",  "role": "ATHLETE", "key": "atleta_meteors4"},
    {"email": "atleta.meteors5@test.com", "username": "atleta_meteors5", "first_name": "Patricia",  "last_name": "Guerrero", "role": "ATHLETE", "key": "atleta_meteors5"},
    {"email": "atleta.meteors6@test.com", "username": "atleta_meteors6", "first_name": "Verónica",  "last_name": "Delgado",  "role": "ATHLETE", "key": "atleta_meteors6"},
    {"email": "atleta.meteors7@test.com", "username": "atleta_meteors7", "first_name": "Adriana",   "last_name": "Vázquez",  "role": "ATHLETE", "key": "atleta_meteors7"},
    {"email": "atleta.meteors8@test.com", "username": "atleta_meteors8", "first_name": "Claudia",   "last_name": "Ramos",    "role": "ATHLETE", "key": "atleta_meteors8"},
]

# ─── Equipos ──────────────────────────────────────────────────────────────────

TEAMS_DATA = [
    {
        "name": "Comets",
        "city": "Guadalajara",
        "phone": "3312345678",
        "address": "Av. Andrómeda 100, Col. Satélite",
        "hc_key": "hc_comets",
        "coaches": ["coach_comets1", "coach_comets2"],
        "athletes": [f"atleta_comets{i}" for i in range(1, 9)],
    },
    {
        "name": "Supernovas",
        "city": "Monterrey",
        "phone": "8187654321",
        "address": "Blvd. Nebulosa 200, Col. Cósmica",
        "hc_key": "hc_supernovas",
        "coaches": ["coach_supernovas1", "coach_supernovas2"],
        "athletes": [f"atleta_supernovas{i}" for i in range(1, 9)],
    },
    {
        "name": "Meteors",
        "city": "Puebla",
        "phone": "2221234567",
        "address": "Calle Meteoro 50, Col. Orión",
        "hc_key": "hc_meteors",
        "coaches": ["coach_meteors1", "coach_meteors2"],
        "athletes": [f"atleta_meteors{i}" for i in range(1, 9)],
    },
]

# ─── Medidas de atletas (8 sets, se asignan por índice) ───────────────────────
# (estatura, pecho, cintura, cadera, entrepierna, ancho-hombros, talla-zapato, peso)

MEASUREMENT_SETS = [
    {"estatura": "162", "pecho": "84", "cintura": "66", "cadera": "90", "entrepierna": "72", "ancho-hombros": "38", "talla-zapato": "25", "peso": "55"},
    {"estatura": "158", "pecho": "80", "cintura": "62", "cadera": "86", "entrepierna": "68", "ancho-hombros": "36", "talla-zapato": "24", "peso": "51"},
    {"estatura": "165", "pecho": "88", "cintura": "68", "cadera": "94", "entrepierna": "76", "ancho-hombros": "40", "talla-zapato": "26", "peso": "58"},
    {"estatura": "160", "pecho": "82", "cintura": "64", "cadera": "88", "entrepierna": "70", "ancho-hombros": "37", "talla-zapato": "25", "peso": "53"},
    {"estatura": "170", "pecho": "90", "cintura": "70", "cadera": "96", "entrepierna": "78", "ancho-hombros": "41", "talla-zapato": "27", "peso": "62"},
    {"estatura": "155", "pecho": "78", "cintura": "60", "cadera": "84", "entrepierna": "66", "ancho-hombros": "35", "talla-zapato": "23", "peso": "48"},
    {"estatura": "168", "pecho": "86", "cintura": "68", "cadera": "92", "entrepierna": "74", "ancho-hombros": "39", "talla-zapato": "26", "peso": "60"},
    {"estatura": "163", "pecho": "83", "cintura": "65", "cadera": "89", "entrepierna": "71", "ancho-hombros": "38", "talla-zapato": "25", "peso": "54"},
]


class Command(BaseCommand):
    help = "Crea equipos, atletas con mediciones y nuevos eventos de prueba"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra los datos de este seed antes de recrearlos",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== seed_full_data ==="))

        with transaction.atomic():
            if options["reset"]:
                self._reset()

            roles = self._check_roles()
            users = self._seed_users(roles)
            teams = self._seed_teams(users)
            self._seed_athlete_profiles_and_measurements(users, teams)
            self._seed_events(users, teams)

        self.stdout.write(self.style.SUCCESS("\nOK: seed_full_data completado."))
        self.stdout.write("  Contraseña de todos los usuarios: Test1234!")

    # ═══════════════════════════════════════════════════════════════
    # RESET
    # ═══════════════════════════════════════════════════════════════

    def _reset(self):
        from events.models import Event, EventCategory, EventTeamRegistration, EventParticipant, EventJudgingCriteria
        from teams.models import Team

        self.stdout.write(self.style.WARNING("  [RESET] Borrando datos del seed..."))

        # 1. Identificar eventos a borrar
        events_to_del = Event.objects.filter(name__in=EVENT_NAMES)

        # 2. Borrar dependencias protegidas de esos eventos
        EventParticipant.objects.filter(event__in=events_to_del).delete()
        EventTeamRegistration.objects.filter(event__in=events_to_del).delete()
        EventCategory.objects.filter(event__in=events_to_del).delete()
        EventJudgingCriteria.objects.filter(event__in=events_to_del).delete()

        # 3. Ahora sí, borrar los eventos
        deleted_events, _ = events_to_del.delete()
        self.stdout.write(f"    Eventos eliminados: {deleted_events}")

        team_names = [t["name"] for t in TEAMS_DATA]
        deleted_teams, _ = Team.objects.filter(name__in=team_names).delete()
        self.stdout.write(f"    Equipos eliminados: {deleted_teams}")

        deleted_users, _ = User.objects.filter(email__in=TEST_EMAILS_FULL).delete()
        self.stdout.write(f"    Usuarios eliminados: {deleted_users}")
        self.stdout.write(self.style.WARNING("  [RESET] Listo.\n"))

    # ═══════════════════════════════════════════════════════════════
    # 1. ROLES
    # ═══════════════════════════════════════════════════════════════

    def _check_roles(self):
        from accounts.models import Role

        self.stdout.write(self.style.MIGRATE_LABEL("\n[1/5] Roles"))
        needed = ["ADMIN", "HEADCOACH", "COACH", "ATHLETE"]
        roles = {}
        for name in needed:
            try:
                roles[name] = Role.objects.get(name=name)
                self.stdout.write(f"    {name}: OK")
            except Role.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"    Rol {name} no encontrado. Ejecuta seed_roles primero."
                    )
                )
        return roles

    # ═══════════════════════════════════════════════════════════════
    # 2. USUARIOS
    # ═══════════════════════════════════════════════════════════════

    def _seed_users(self, roles):
        self.stdout.write(self.style.MIGRATE_LABEL("\n[2/5] Usuarios"))

        users = {}
        for data in USERS_DATA:
            key = data["key"]
            role_name = data["role"]

            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "username": data["username"],
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "profile_completed": False,
                    "privacy_accepted": True,
                    "terms_accepted": True,
                },
            )

            if created:
                user.set_password("Test1234!")
                user.save(update_fields=["password"])
                if role_name in roles:
                    user.roles.add(roles[role_name])
                self.stdout.write(
                    self.style.SUCCESS(f"    CREADO: {user.email} [{role_name}]")
                )
            else:
                self.stdout.write(f"    ya existe: {user.email}")

            users[key] = user

        return users

    # ═══════════════════════════════════════════════════════════════
    # 3. EQUIPOS
    # ═══════════════════════════════════════════════════════════════

    def _seed_teams(self, users):
        from teams.models import Team, UserTeamMembership

        self.stdout.write(self.style.MIGRATE_LABEL("\n[3/5] Equipos"))

        teams = {}
        for data in TEAMS_DATA:
            headcoach = users[data["hc_key"]]

            team, created = Team.objects.get_or_create(
                name=data["name"],
                defaults={
                    "coach": headcoach,
                    "city": data["city"],
                    "phone": data["phone"],
                    "address": data["address"],
                    "is_active": True,
                },
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"    Equipo CREADO: {team.name} (código: {team.join_code})"
                    )
                )
            else:
                self.stdout.write(f"    Equipo ya existe: {team.name}")

            # Membresías — coaches
            for coach_key in data["coaches"]:
                if coach_key not in users:
                    continue
                UserTeamMembership.objects.get_or_create(
                    user=users[coach_key],
                    team=team,
                    defaults={"role_in_team": "COACH", "status": "accepted", "is_active": True},
                )

            # Membresías — atletas
            for athlete_key in data["athletes"]:
                if athlete_key not in users:
                    continue
                UserTeamMembership.objects.get_or_create(
                    user=users[athlete_key],
                    team=team,
                    defaults={"role_in_team": "ATHLETE", "status": "accepted", "is_active": True},
                )

            member_count = team.memberships.filter(is_active=True).count()
            self.stdout.write(f"      Miembros activos: {member_count}")
            teams[data["name"]] = team

        return teams

    # ═══════════════════════════════════════════════════════════════
    # 4. PERFILES DE ATLETA + MEDICIONES
    # ═══════════════════════════════════════════════════════════════

    def _seed_athlete_profiles_and_measurements(self, users, teams):
        from accounts.models import AthleteProfile
        from measures.models import MeasurementField, MeasurementValue

        self.stdout.write(self.style.MIGRATE_LABEL("\n[4/5] Perfiles de atleta y mediciones"))

        # Cargar campos de medición
        measure_fields = {f.slug: f for f in MeasurementField.objects.filter(is_active=True)}
        if not measure_fields:
            self.stdout.write(
                self.style.WARNING(
                    "    No hay campos de medición. Ejecuta seed_products primero."
                )
            )

        created_profiles = 0
        created_measurements = 0

        for team_data in TEAMS_DATA:
            for idx, athlete_key in enumerate(team_data["athletes"]):
                if athlete_key not in users:
                    continue
                athlete = users[athlete_key]

                # AthleteProfile
                profile, p_created = AthleteProfile.objects.get_or_create(
                    user=athlete,
                    defaults={
                        "emergency_contact": f"Familiar de {athlete.first_name}",
                        "emergency_phone": "5500000000",
                        "is_active_competitor": True,
                    },
                )
                if p_created:
                    created_profiles += 1

                # MeasurementValues — usa el set correspondiente al índice
                measurement_set = MEASUREMENT_SETS[idx % len(MEASUREMENT_SETS)]
                for slug, value in measurement_set.items():
                    if slug not in measure_fields:
                        continue
                    _, mv_created = MeasurementValue.objects.get_or_create(
                        user=athlete,
                        field=measure_fields[slug],
                        defaults={"value": value},
                    )
                    if mv_created:
                        created_measurements += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"    Perfiles creados: {created_profiles}  |  "
                f"Mediciones creadas: {created_measurements}"
            )
        )

    # ═══════════════════════════════════════════════════════════════
    # 5. EVENTOS
    # ═══════════════════════════════════════════════════════════════

    def _seed_events(self, users, teams):
        from events.models import (
            Event,
            EventCategory,
            EventJudgingCriteria,
            EventTeamRegistration,
        )
        from teams.models import TeamCategory

        self.stdout.write(self.style.MIGRATE_LABEL("\n[5/5] Eventos"))

        # Buscamos al admin de test para usar como organizador;
        # si no existe, usamos el headcoach de Comets.
        organizer = (
            User.objects.filter(email="admin@test.com").first()
            or users["hc_comets"]
        )

        today = datetime.date.today()

        self._seed_grand_prix(
            organizer, teams, today, EventCategory, EventJudgingCriteria, EventTeamRegistration, TeamCategory
        )
        self._seed_copa_galaxia(
            organizer, teams, today, EventCategory, EventJudgingCriteria, EventTeamRegistration, TeamCategory
        )

    # ─── Grand Prix Espacial 2026 (inscripciones abiertas) ────────

    def _seed_grand_prix(self, organizer, teams, today, EventCategory, EventJudgingCriteria, EventTeamRegistration, TeamCategory):
        from events.models import Event

        name = EVENT_NAMES[0]
        # Inscripciones abiertas desde hace 5 días — competencia el 14 y 15 de junio 2026
        reg_open  = today - datetime.timedelta(days=5)
        reg_close = datetime.date(2026, 5, 31)
        start     = datetime.date(2026, 6, 14)
        end       = datetime.date(2026, 6, 15)

        try:
            event = Event.objects.get(name=name)
            event.start_date = start
            event.end_date = end
            event.registration_open = reg_open
            event.registration_close = reg_close
            event.status = Event.STATUS_REGISTRATION_OPEN
            event.save()
            self.stdout.write(f"    Evento ya existe, fechas actualizadas: {name}")
        except Event.DoesNotExist:
            event = Event(
                name=name,
                description="Gran Premio nacional de cheerleading. Evento de prueba generado por seed.",
                event_type=Event.TYPE_COMPETITION,
                status=Event.STATUS_REGISTRATION_OPEN,
                organizer=organizer,
                venue_name="Auditorio Galaxia",
                venue_address="Av. Cosmos 500",
                venue_city="Ciudad de México",
                start_date=start,
                end_date=end,
                registration_open=reg_open,
                registration_close=reg_close,
                max_teams=24,
            )
            event.save()
            self.stdout.write(self.style.SUCCESS(f"    Evento CREADO: {name}"))

        # Categorías con FK a TeamCategory (opcional)
        categories_config = [
            ("Juvenil Nivel 1", "Juvenil Nivel 1", 6, 1),
            ("Juvenil Nivel 2", "Juvenil Nivel 2", 8, 2),
            ("Senior Nivel 1",  "Senior Nivel 1",  6, 3),
        ]

        event_categories = {}
        for cat_name, tc_name, max_t, order in categories_config:
            team_cat = TeamCategory.objects.filter(name=tc_name).first()
            cat, created = EventCategory.objects.get_or_create(
                event=event,
                name=cat_name,
                defaults={
                    "team_category": team_cat,
                    "max_teams": max_t,
                    "description": f"Categoría {cat_name} del Grand Prix",
                    "order": order,
                },
            )
            event_categories[cat_name] = cat
            if created:
                self.stdout.write(self.style.SUCCESS(f"      Categoría CREADA: {cat_name}"))

        # Criterios de evaluación
        criteria_config = [
            ("Técnica",          "Calidad técnica de los movimientos", 30, "30.00", 1),
            ("Sincronización",   "Precisión en equipo",                25, "25.00", 2),
            ("Dificultad",       "Nivel de dificultad de la rutina",   25, "25.00", 3),
            ("Presentación",     "Uniformes, formación y actitud",     20, "20.00", 4),
        ]
        for crit_name, desc, weight, max_score, order in criteria_config:
            EventJudgingCriteria.objects.get_or_create(
                event=event,
                name=crit_name,
                defaults={
                    "description": desc,
                    "weight": weight,
                    "max_score": max_score,
                    "order": order,
                    "is_active": True,
                },
            )

        self.stdout.write(f"      Criterios de evaluación: {event.judging_criteria.count()}")

    # ─── Copa Galaxia 2026 (completada, para probar resultados) ───

    def _seed_copa_galaxia(self, organizer, teams, today, EventCategory, EventJudgingCriteria, EventTeamRegistration, TeamCategory):
        from decimal import Decimal
        from events.models import Event, EventResult, EventScore

        name = EVENT_NAMES[1]
        # Copa completada — Guadalajara, 5-6 de abril 2026
        reg_open  = datetime.date(2026, 2, 1)
        reg_close = datetime.date(2026, 3, 20)
        start     = datetime.date(2026, 4, 5)
        end       = datetime.date(2026, 4, 6)

        try:
            event = Event.objects.get(name=name)
            self.stdout.write(f"    Evento ya existe: {name}")
        except Event.DoesNotExist:
            event = Event(
                name=name,
                description="Copa Galaxia — evento completado. Datos de prueba para módulo de resultados.",
                event_type=Event.TYPE_COMPETITION,
                status=Event.STATUS_COMPLETED,
                organizer=organizer,
                venue_name="Arena Nebulosa",
                venue_address="Blvd. Estelar 300",
                venue_city="Guadalajara",
                start_date=start,
                end_date=end,
                registration_open=reg_open,
                registration_close=reg_close,
                max_teams=12,
            )
            event.save()
            self.stdout.write(self.style.SUCCESS(f"    Evento CREADO: {name}"))

        # Categoría
        team_cat = TeamCategory.objects.filter(name="Juvenil Nivel 2").first()
        categoria, _ = EventCategory.objects.get_or_create(
            event=event,
            name="Juvenil Nivel 2",
            defaults={
                "team_category": team_cat,
                "max_teams": 6,
                "description": "Categoría juvenil nivel 2",
                "order": 1,
            },
        )

        # Criterios
        criteria_config = [
            ("Técnica",       "Calidad técnica", 40, "40.00", 1),
            ("Presentación",  "Imagen general",  30, "30.00", 2),
            ("Dificultad",    "Nivel rutina",    30, "30.00", 3),
        ]
        criterios = {}
        for cname, desc, weight, max_score, order in criteria_config:
            c, _ = EventJudgingCriteria.objects.get_or_create(
                event=event,
                name=cname,
                defaults={"description": desc, "weight": weight, "max_score": max_score, "order": order, "is_active": True},
            )
            criterios[cname] = c

        # Registros de equipos + resultados ficticios
        team_results = [
            ("Comets",     1, Decimal("92.50")),
            ("Supernovas", 2, Decimal("88.00")),
            ("Meteors",    3, Decimal("84.75")),
        ]

        for team_name, placement, total_score in team_results:
            team = teams.get(team_name)
            if not team:
                continue

            reg, reg_created = EventTeamRegistration.objects.get_or_create(
                event=event,
                team=team,
                defaults={
                    "category": categoria,
                    "status": EventTeamRegistration.STATUS_ACCEPTED,
                    "registered_by": team.coach,
                    "notes": "Registro seed",
                },
            )

            # Resultado
            EventResult.objects.get_or_create(
                team_registration=reg,
                category=categoria,
                round=EventResult.ROUND_FINAL,
                defaults={
                    "placement": placement,
                    "total_score": total_score,
                    "published": True,
                    "published_at": datetime.datetime.now(tz=datetime.timezone.utc),
                },
            )

            # Scores por criterio (usamos al headcoach como juez ficticio)
            judge = team.coach
            score_values = {
                "Técnica":      [Decimal("38.0"), Decimal("35.0"), Decimal("33.0")][placement - 1],
                "Presentación": [Decimal("28.5"), Decimal("27.0"), Decimal("26.0")][placement - 1],
                "Dificultad":   [Decimal("26.0"), Decimal("26.0"), Decimal("25.75")][placement - 1],
            }
            for cname, score_val in score_values.items():
                if cname not in criterios:
                    continue
                EventScore.objects.get_or_create(
                    team_registration=reg,
                    criteria=criterios[cname],
                    judge=judge,
                    round=EventScore.ROUND_FINAL,
                    defaults={"score": score_val, "notes": "Score seed"},
                )

        self.stdout.write(
            f"      Registros: {event.team_registrations.count()}  |  "
            f"Resultados: {EventResult.objects.filter(team_registration__event=event).count()}"
        )
