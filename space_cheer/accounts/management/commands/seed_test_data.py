# accounts/management/commands/seed_test_data.py
"""
Management command para poblar la base de datos con datos de prueba realistas.

Uso:
    python manage.py seed_test_data
    python manage.py seed_test_data --reset   # borra los datos de prueba antes de recrearlos

Idempotente: se puede correr múltiples veces sin duplicar datos.

Orden de creación:
    1. Roles (ADMIN, HEADCOACH, COACH, ATHLETE)
    2. Usuarios de prueba (admin, headcoach, 2 coaches, 5 atletas)
    3. Equipo "Galaxies" con membresías
    4. Evento de prueba con categoría

NOTA IMPORTANTE:
    Los roles HEADCOACH y COACH tienen requires_curp=True en producción.
    En este seed omitimos la CURP para datos de prueba, creando usuarios
    con profile_completed=False para evitar la validación de clean().
    Esto es intencional para testing.
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()

# ─── Identificadores de los datos de prueba ───────────────────────────────────
# Usar prefijo claro para poder limpiarlos con --reset
TEST_EMAILS = [
    "admin@test.com",
    "headcoach@test.com",
    "coach1@test.com",
    "coach2@test.com",
    "atleta1@test.com",
    "atleta2@test.com",
    "atleta3@test.com",
    "atleta4@test.com",
    "atleta5@test.com",
]

TEST_TEAM_NAME = "Galaxies"
TEST_EVENT_NAME = "Torneo Espacial 2026 — SEED"


class Command(BaseCommand):
    help = "Pobla la base de datos con datos de prueba (idempotente)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Borra todos los datos de prueba antes de recrearlos. "
                "Solo afecta usuarios/equipo/evento del seed, no datos reales."
            ),
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== seed_test_data ==="))

        with transaction.atomic():
            if options["reset"]:
                self._reset_test_data()

            roles = self._seed_roles()
            users = self._seed_users(roles)
            team = self._seed_team(users)
            self._seed_event(users)

        self.stdout.write(self.style.SUCCESS("\n✔ seed_test_data completado sin errores."))
        self.stdout.write(
            "  Usuarios de prueba listos con contraseña Test1234! "
            "(admin: Admin1234!)"
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # 1. RESET
    # ═══════════════════════════════════════════════════════════════════════════

    def _reset_test_data(self):
        """
        Borra los datos de prueba identificables.
        Opera en orden inverso para respetar FK constraints.
        """
        from events.models import Event
        from teams.models import Team

        self.stdout.write(self.style.WARNING("  [RESET] Borrando datos de prueba..."))

        # Evento de prueba
        deleted_events, _ = Event.objects.filter(name=TEST_EVENT_NAME).delete()
        self.stdout.write(f"    Eventos eliminados: {deleted_events}")

        # Equipo de prueba (CASCADE elimina membresías)
        deleted_teams, _ = Team.objects.filter(name=TEST_TEAM_NAME).delete()
        self.stdout.write(f"    Equipos eliminados: {deleted_teams}")

        # Usuarios de prueba
        deleted_users, _ = User.objects.filter(email__in=TEST_EMAILS).delete()
        self.stdout.write(f"    Usuarios eliminados: {deleted_users}")

        self.stdout.write(self.style.WARNING("  [RESET] Listo.\n"))

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. ROLES
    # ═══════════════════════════════════════════════════════════════════════════

    def _seed_roles(self) -> dict:
        """
        Crea los 4 roles principales si no existen.
        Idempotente via get_or_create.

        Retorna dict {nombre: Role} para usarlo al asignar usuarios.
        """
        from accounts.models import Role

        self.stdout.write(self.style.MIGRATE_LABEL("\n[1/4] Roles"))

        # Configuración mínima necesaria para datos de prueba.
        # El comando seed_roles crea la lista completa con flags correctos;
        # aquí solo nos aseguramos que existan los 4 esenciales.
        role_configs = [
            {
                "name": "ADMIN",
                "defaults": {
                    "is_staff_type": True,
                    "is_coach_type": False,
                    "is_athlete_type": False,
                    "requires_curp": False,
                    "allow_dashboard_access": True,
                },
            },
            {
                "name": "HEADCOACH",
                "defaults": {
                    "is_staff_type": False,
                    "is_coach_type": True,
                    "is_athlete_type": False,
                    "requires_curp": True,
                    "allow_dashboard_access": True,
                },
            },
            {
                "name": "COACH",
                "defaults": {
                    "is_staff_type": False,
                    "is_coach_type": True,
                    "is_athlete_type": False,
                    "requires_curp": True,
                    "allow_dashboard_access": True,
                },
            },
            {
                "name": "ATHLETE",
                "defaults": {
                    "is_staff_type": False,
                    "is_coach_type": False,
                    "is_athlete_type": True,
                    "requires_curp": True,
                    "allow_dashboard_access": True,
                },
            },
        ]

        roles = {}
        for config in role_configs:
            role, created = Role.objects.get_or_create(
                name=config["name"],
                defaults=config["defaults"],
            )
            roles[config["name"]] = role
            status = "CREADO" if created else "ya existe"
            self.stdout.write(f"    Rol {config['name']}: {status}")

        return roles

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. USUARIOS
    # ═══════════════════════════════════════════════════════════════════════════

    def _seed_users(self, roles: dict) -> dict:
        """
        Crea los 9 usuarios de prueba.
        Usa get_or_create por email para idempotencia.

        profile_completed=False para evitar que clean() exija CURP
        (los roles HEADCOACH/COACH tienen requires_curp=True en producción).

        Retorna dict con las instancias de usuario para uso posterior.
        """
        self.stdout.write(self.style.MIGRATE_LABEL("\n[2/4] Usuarios"))

        # Definición de todos los usuarios de prueba
        users_config = [
            # --- Admin ---
            {
                "email": "admin@test.com",
                "username": "admin_test",
                "password": "Admin1234!",
                "first_name": "Admin",
                "last_name": "Sistema",
                "role_names": ["ADMIN"],
                "is_staff": True,
                "key": "admin",
            },
            # --- Head Coach ---
            {
                "email": "headcoach@test.com",
                "username": "headcoach_test",
                "password": "Test1234!",
                "first_name": "Luna",
                "last_name": "Estrella",
                "role_names": ["HEADCOACH"],
                "key": "headcoach",
            },
            # --- Coaches ---
            {
                "email": "coach1@test.com",
                "username": "coach1_test",
                "password": "Test1234!",
                "first_name": "Andrés",
                "last_name": "Nebula",
                "role_names": ["COACH"],
                "key": "coach1",
            },
            {
                "email": "coach2@test.com",
                "username": "coach2_test",
                "password": "Test1234!",
                "first_name": "Sofía",
                "last_name": "Cosmos",
                "role_names": ["COACH"],
                "key": "coach2",
            },
            # --- Atletas ---
            {
                "email": "atleta1@test.com",
                "username": "atleta1_test",
                "password": "Test1234!",
                "first_name": "Valentina",
                "last_name": "Aurora",
                "role_names": ["ATHLETE"],
                "key": "atleta1",
            },
            {
                "email": "atleta2@test.com",
                "username": "atleta2_test",
                "password": "Test1234!",
                "first_name": "Camila",
                "last_name": "Vega",
                "role_names": ["ATHLETE"],
                "key": "atleta2",
            },
            {
                "email": "atleta3@test.com",
                "username": "atleta3_test",
                "password": "Test1234!",
                "first_name": "Isabella",
                "last_name": "Nova",
                "role_names": ["ATHLETE"],
                "key": "atleta3",
            },
            {
                "email": "atleta4@test.com",
                "username": "atleta4_test",
                "password": "Test1234!",
                "first_name": "Mariana",
                "last_name": "Quasar",
                "role_names": ["ATHLETE"],
                "key": "atleta4",
            },
            {
                "email": "atleta5@test.com",
                "username": "atleta5_test",
                "password": "Test1234!",
                "first_name": "Gabriela",
                "last_name": "Pulsar",
                "role_names": ["ATHLETE"],
                "key": "atleta5",
            },
        ]

        users = {}
        for config in users_config:
            key = config.pop("key")
            role_names = config.pop("role_names")
            password = config.pop("password")
            is_staff = config.pop("is_staff", False)

            # get_or_create por email (campo único en el modelo)
            user, created = User.objects.get_or_create(
                email=config["email"],
                defaults={
                    "username": config["username"],
                    "first_name": config["first_name"],
                    "last_name": config["last_name"],
                    # profile_completed=False evita que clean() exija CURP
                    # ya que los roles HEADCOACH/COACH/ATHLETE tienen requires_curp=True
                    "profile_completed": False,
                    "is_staff": is_staff,
                    "privacy_accepted": True,
                    "terms_accepted": True,
                },
            )

            if created:
                # Establecer contraseña (hash bcrypt/PBKDF2)
                user.set_password(password)
                user.save(update_fields=["password"])

                # Asignar roles vía M2M
                for role_name in role_names:
                    if role_name in roles:
                        user.roles.add(roles[role_name])

                self.stdout.write(
                    self.style.SUCCESS(
                        f"    CREADO: {user.email} [{', '.join(role_names)}]"
                    )
                )
            else:
                self.stdout.write(f"    ya existe: {user.email}")

            users[key] = user

        return users

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. EQUIPO
    # ═══════════════════════════════════════════════════════════════════════════

    def _seed_team(self, users: dict):
        """
        Crea el equipo "Galaxies" con el headcoach como dueño (campo coach).
        Agrega coaches y atletas como miembros con status 'accepted'.

        UserTeamMembership tiene unique_together (user, team), así que
        get_or_create es seguro para idempotencia.
        """
        from teams.models import Team, UserTeamMembership

        self.stdout.write(self.style.MIGRATE_LABEL("\n[3/4] Equipo"))

        headcoach = users["headcoach"]

        # El modelo Team requiere: name, coach, city, phone
        # join_code se genera automáticamente en save()
        team, created = Team.objects.get_or_create(
            name=TEST_TEAM_NAME,
            defaults={
                "coach": headcoach,
                "city": "Ciudad de México",
                "phone": "5512345678",
                "address": "Av. Universo 42, Col. Espacial",
                "is_active": True,
            },
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"    Equipo CREADO: {team.name} (código: {team.join_code})")
            )
        else:
            self.stdout.write(f"    Equipo ya existe: {team.name}")

        # --- Membresías ---
        # Coaches → rol COACH en equipo
        coaches = [users["coach1"], users["coach2"]]
        for coach in coaches:
            membership, created = UserTeamMembership.objects.get_or_create(
                user=coach,
                team=team,
                defaults={
                    "role_in_team": "COACH",
                    "status": "accepted",
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(f"    Membresía CREADA: {coach.email} → {team.name} [COACH]")
            else:
                self.stdout.write(f"    Membresía ya existe: {coach.email}")

        # Atletas → rol ATHLETE en equipo
        atletas = [users[f"atleta{i}"] for i in range(1, 6)]
        for atleta in atletas:
            membership, created = UserTeamMembership.objects.get_or_create(
                user=atleta,
                team=team,
                defaults={
                    "role_in_team": "ATHLETE",
                    "status": "accepted",
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(f"    Membresía CREADA: {atleta.email} → {team.name} [ATHLETE]")
            else:
                self.stdout.write(f"    Membresía ya existe: {atleta.email}")

        return team

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. EVENTO
    # ═══════════════════════════════════════════════════════════════════════════

    def _seed_event(self, users: dict):
        """
        Crea un evento de prueba con una categoría.

        Event.save() llama a full_clean() que valida fechas, así que
        usamos fechas coherentes:
          - registration_open  < registration_close  <= start_date <= end_date

        El organizador es el admin de prueba.
        Usamos update_or_create para actualizar fechas si el evento ya existe
        (de lo contrario, fechas viejas en el pasado serían confusas).
        """
        from events.models import Event, EventCategory

        self.stdout.write(self.style.MIGRATE_LABEL("\n[4/4] Evento"))

        admin_user = users["admin"]
        today = datetime.date.today()

        # Inscripciones abiertas desde hace 3 días, cierran en 3 semanas, evento en 45 días
        reg_open  = today - datetime.timedelta(days=3)
        reg_close = today + datetime.timedelta(days=21)
        start_date = today + datetime.timedelta(days=45)
        end_date   = today + datetime.timedelta(days=46)

        try:
            event = Event.objects.get(name=TEST_EVENT_NAME)
            event.start_date = start_date
            event.end_date = end_date
            event.registration_open = reg_open
            event.registration_close = reg_close
            event.status = Event.STATUS_REGISTRATION_OPEN
            event.save()
            self.stdout.write(f"    Evento ya existe, fechas actualizadas: {event.name}")

        except Event.DoesNotExist:
            event = Event(
                name=TEST_EVENT_NAME,
                description=(
                    "Evento de prueba generado por seed_test_data. "
                    "Seguro de eliminar en producción."
                ),
                event_type=Event.TYPE_COMPETITION,
                status=Event.STATUS_REGISTRATION_OPEN,
                organizer=admin_user,
                venue_name="Arena Galaxia",
                venue_address="Av. Vía Láctea 100",
                venue_city="Ciudad de México",
                start_date=start_date,
                end_date=end_date,
                registration_open=reg_open,
                registration_close=reg_close,
                max_teams=16,
            )
            event.save()
            self.stdout.write(
                self.style.SUCCESS(f"    Evento CREADO: {event.name}")
            )

        # --- Categoría del evento ---
        # EventCategory tiene unique_together (event, name)
        category, cat_created = EventCategory.objects.get_or_create(
            event=event,
            name="Juvenil Nivel 3",
            defaults={
                "description": "Categoría juvenil nivel intermedio",
                "max_teams": 8,
                "order": 1,
            },
        )

        if cat_created:
            self.stdout.write(
                self.style.SUCCESS(f"    Categoría CREADA: {category.name}")
            )
        else:
            self.stdout.write(f"    Categoría ya existe: {category.name}")

        self.stdout.write(
            f"\n    Evento listo:"
            f"\n      Nombre:        {event.name}"
            f"\n      Tipo:          {event.event_type}"
            f"\n      Inscripciones: {reg_open} → {reg_close}"
            f"\n      Evento:        {start_date} → {end_date}"
        )
