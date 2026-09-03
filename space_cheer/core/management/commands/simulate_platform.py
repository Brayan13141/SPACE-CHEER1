"""
Simulación end-to-end de la plataforma Space Cheer sobre la BD local.

Recorre el sistema completo con datos coherentes:
  1. Perfiles completos + CURP para todos los usuarios sembrados
  2. Usuarios nuevos: admin, staff, jueces, tutores y 7 operarios
  3. Configuración de producción: etapas por producto + roles de operario
  4. Pedidos en TODOS los estados (DRAFT → DELIVERED, CANCELLED, OFFLINE)
  5. Producción: jobs asignados, etapas completadas en orden, pausas,
     urgencias y reportes de error con revisión de dirección
  6. Eventos: competencia con inscripciones, jueces y participantes
  7. Hospitalidad: hotel, habitaciones y asignación de camas

Uso:
    python manage.py simulate_platform
    python manage.py simulate_platform --json-out ../SIMULACION.json

Prerrequisitos (en este orden, sobre BD recién migrada):
    python manage.py seed_all
    python manage.py seed_products
    python manage.py seed_full_data

Idempotente en lo posible, pero está pensado para correr una vez sobre una
base recién sembrada: los pedidos se crean siempre nuevos.
"""

import datetime
import io
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

User = get_user_model()

PASSWORD = "Test1234!"

# PNG 1x1 real (magic bytes válidos) para las imágenes de diseño.
# OrderDesignImage exige 35 MB vía validador de formulario; el ORM no corre
# validadores, así que el mockup de simulación pesa bytes en vez de MB.
PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000d49444154789c6360000002000100ffff0300000600"
    "0557bfabd40000000049454e44ae426082"
)

CURP_STATES = ["JC", "NL", "PL", "DF", "MC", "GT", "VZ", "SL"]
CURP_CONSONANTS = ["RZL", "PRZ", "MRT", "GNZ", "SNC", "TRR", "VLD", "CRZ"]


def make_curp(index: int, gender: str, birth: datetime.date) -> str:
    """CURP sintética que cumple el regex del modelo User (18 caracteres)."""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    a = letters[index % 26]
    b = letters[(index // 26) % 26]
    c = letters[(index // 7) % 26]
    d = letters[(index // 11) % 26]
    digits = birth.strftime("%y%m%d")
    state = CURP_STATES[index % len(CURP_STATES)]
    cons = CURP_CONSONANTS[index % len(CURP_CONSONANTS)]
    alnum = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[index % 36]
    check = str(index % 10)
    return f"{a}{b}{c}{d}{digits}{gender}{state}{cons}{alnum}{check}"


class Command(BaseCommand):
    help = "Simula la plataforma Space Cheer completa sobre la base local"

    def add_arguments(self, parser):
        parser.add_argument(
            "--json-out",
            type=str,
            default="",
            help="Ruta donde volcar el resumen de la simulación en JSON",
        )

    # ==================================================================
    # ENTRY POINT
    # ==================================================================
    def handle(self, *args, **options):
        self.report = {
            "generated_at": timezone.now().isoformat(),
            "password": PASSWORD,
            "users": [],
            "teams": [],
            "orders": [],
            "production": [],
            "error_reports": [],
            "events": [],
            "hospitality": [],
        }
        self._phone_seq = 5500000000
        self._curp_seq = 0

        self.h("FASE 1 — Perfiles y usuarios")
        self.phase_users()

        self.h("FASE 2 — Configuración de producción")
        self.phase_production_config()

        self.h("FASE 3 — Pedidos")
        self.phase_orders()

        self.h("FASE 4 — Piso de producción")
        self.phase_production_floor()
        # Las órdenes A e I cambian de estado DENTRO de la fase 4 (se entregan
        # cuando su job cierra), así que el reporte se reconstruye desde la BD.
        self.rebuild_orders_report()

        self.h("FASE 5 — Eventos y concursos")
        self.phase_events()

        self.h("FASE 6 — Hospitalidad")
        self.phase_hospitality()

        out = options["json_out"]
        if out:
            with io.open(out, "w", encoding="utf-8") as fh:
                json.dump(self.report, fh, ensure_ascii=False, indent=2)
            self.ok(f"Resumen JSON escrito en {out}")

        self.h("RESUMEN")
        self.stdout.write(f"  Usuarios documentados : {len(self.report['users'])}")
        self.stdout.write(f"  Pedidos               : {len(self.report['orders'])}")
        self.stdout.write(f"  Jobs de producción    : {len(self.report['production'])}")
        self.stdout.write(f"  Reportes de error     : {len(self.report['error_reports'])}")
        self.stdout.write(f"  Eventos               : {len(self.report['events'])}")

    # ==================================================================
    # HELPERS DE SALIDA
    # ==================================================================
    def h(self, text):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {text} ==="))

    def ok(self, text):
        self.stdout.write(self.style.SUCCESS(f"  {text}"))

    def info(self, text):
        self.stdout.write(f"  {text}")

    def warn(self, text):
        self.stdout.write(self.style.WARNING(f"  {text}"))

    # ==================================================================
    # HELPERS DE DATOS
    # ==================================================================
    def next_phone(self):
        self._phone_seq += 1
        return str(self._phone_seq)

    def next_curp(self, gender, birth):
        self._curp_seq += 1
        return make_curp(self._curp_seq, gender, birth)

    def complete_profile(self, user, *, gender, birth, city="Guadalajara",
                         address="Av. Andrómeda 100", zip_code="44100"):
        """Deja al usuario listo para entrar: CURP, teléfono, dirección default
        y su correo ya verificado en allauth."""
        from accounts.models import UserAddress

        if not user.phone:
            user.phone = self.next_phone()
        if not user.birth_date:
            user.birth_date = birth
        if not user.gender:
            user.gender = gender
        if not user.curp:
            user.curp = self.next_curp(gender, birth)
        user.privacy_accepted = True
        user.terms_accepted = True
        user.profile_completed = True
        user.save()

        if not UserAddress.objects.filter(user=user, is_default=True).exists():
            UserAddress.objects.create(
                user=user,
                label="Casa",
                address=address,
                city=city,
                zip_code=zip_code,
                is_default=True,
            )

        self.verify_email(user)
        return user

    @staticmethod
    def verify_email(user):
        """Marca el correo como verificado y primario en allauth.

        El `.env` local trae ACCOUNT_EMAIL_VERIFICATION=none, pero el default
        del settings es "mandatory": sin esto, la simulación deja de poder
        entrar en cuanto alguien corre con la configuración por defecto.
        """
        from allauth.account.models import EmailAddress

        if not user.email:
            return
        EmailAddress.objects.update_or_create(
            user=user,
            email=user.email,
            defaults={"verified": True, "primary": True},
        )

    def record_user(self, user, role, note, team=""):
        self.report["users"].append({
            "email": user.email,
            "username": user.username,
            "name": user.get_full_name(),
            "role": role,
            "team": team,
            "note": note,
        })

    def get_or_create_user(self, *, email, username, first, last, role_name,
                           gender, birth, superuser=False):
        from accounts.models import Role

        user = User.objects.filter(email=email).first()
        created = False
        if user is None:
            user = User(
                email=email,
                username=username,
                first_name=first,
                last_name=last,
            )
            user.set_password(PASSWORD)
            if superuser:
                user.is_superuser = True
                user.is_staff = True
            user.save()
            created = True

        role = Role.objects.filter(name=role_name).first()
        if role and not user.roles.filter(pk=role.pk).exists():
            user.roles.add(role)

        self.complete_profile(user, gender=gender, birth=birth)
        if created:
            self.ok(f"CREADO {email} [{role_name}]")
        else:
            self.info(f"ya existe {email} [{role_name}]")
        return user

    # ==================================================================
    # FASE 1 — USUARIOS
    # ==================================================================
    def phase_users(self):
        from accounts.models import AthleteProfile, AthleteMedicalInfo, CoachProfile, StaffProfile
        from custody.models import Guardianship
        from teams.models import Team, UserTeamMembership

        today = datetime.date.today()

        # ── Admin y staff ────────────────────────────────────────────
        self.admin = self.get_or_create_user(
            email="admin@test.com", username="admin", first="Bryan", last="Sánchez",
            role_name="ADMIN", gender="H", birth=datetime.date(1990, 3, 12),
            superuser=True,
        )
        self.record_user(self.admin, "ADMIN", "Superusuario. Aprueba diseños, manda a producción, entrega, revisa reportes de error.")

        self.staff = self.get_or_create_user(
            email="staff@test.com", username="staff_ops", first="Renata", last="Galindo",
            role_name="STAFF", gender="M", birth=datetime.date(1995, 7, 4),
        )
        StaffProfile.objects.get_or_create(user=self.staff)
        self.record_user(self.staff, "STAFF", "Staff de oficina. Captura pedidos offline y da seguimiento.")

        # ── Jueces ───────────────────────────────────────────────────
        self.judges = []
        judge_data = [
            ("juez1@test.com", "juez1", "Elena", "Castaño", "M", datetime.date(1985, 1, 20)),
            ("juez2@test.com", "juez2", "Ricardo", "Fuentes", "H", datetime.date(1982, 9, 8)),
            ("juez3@test.com", "juez3", "Mónica", "Beltrán", "M", datetime.date(1988, 11, 30)),
        ]
        for email, uname, first, last, gender, birth in judge_data:
            j = self.get_or_create_user(
                email=email, username=uname, first=first, last=last,
                role_name="JUEZ", gender=gender, birth=birth,
            )
            self.judges.append(j)
            self.record_user(j, "JUEZ", "Panel de jueces del Grand Prix. Califica por criterio.")

        # ── Perfiles completos de coaches y atletas sembrados ────────
        teams = {t.name: t for t in Team.objects.filter(name__in=["Comets", "Supernovas", "Meteors"])}
        self.teams = teams

        for team in teams.values():
            # El head coach entra al equipo como COACH, que es un valor real de
            # ROLE_CHOICES. Su cargo de head coach sale de Team.coach, no de un
            # literal en la membresía: sembrar "HEADCOACH" aquí metía en la base
            # justo el dato fuera de spec que las reglas dejaron de reconocer.
            UserTeamMembership.objects.get_or_create(
                user=team.coach, team=team,
                defaults={"role_in_team": "COACH", "status": "accepted", "is_active": True},
            )
            self.complete_profile(team.coach, gender="H", birth=datetime.date(1988, 5, 15), city=team.city)
            CoachProfile.objects.get_or_create(
                user=team.coach,
                defaults={"status": CoachProfile.APPROVED},
            )
            self.record_user(team.coach, "HEADCOACH",
                             f"Head coach de {team.name}. Crea pedidos del equipo y aprueba el diseño.",
                             team=team.name)

        for m in UserTeamMembership.objects.filter(team__in=teams.values()).select_related("user", "team"):
            u = m.user
            # El head coach ya se documentó arriba; su membresía COACH no debe
            # generar una segunda entrada en el reporte.
            if u.pk == m.team.coach_id:
                continue
            if m.role_in_team == "COACH":
                self.complete_profile(u, gender="M", birth=datetime.date(1993, 2, 10), city=m.team.city)
                CoachProfile.objects.get_or_create(user=u, defaults={"status": CoachProfile.APPROVED})
                self.record_user(u, "COACH", f"Coach auxiliar de {m.team.name}. Captura medidas de atletas.", team=m.team.name)
            elif m.role_in_team == "ATHLETE":
                # Menores de edad: fuerza el flujo de tutor.
                birth = today - datetime.timedelta(days=365 * 16 + (u.pk % 300))
                self.complete_profile(u, gender="M", birth=birth, city=m.team.city)
                prof, _ = AthleteProfile.objects.get_or_create(
                    user=u,
                    defaults={
                        "emergency_contact": f"Familia {u.last_name}",
                        "emergency_phone": self.next_phone(),
                    },
                )
                AthleteMedicalInfo.objects.get_or_create(
                    athlete=prof,
                    defaults={"has_insurance": True, "insurance_policy_number": f"POL-{u.pk:05d}"},
                )
                self.record_user(u, "ATHLETE", f"Atleta menor de edad de {m.team.name}. Medidas cargadas.", team=m.team.name)

        # ── Tutores ligados a atletas menores ────────────────────────
        self.guardians = []
        guardian_data = [
            ("tutor.comets@test.com", "tutor_comets", "Alicia", "Cruz", "M", "Comets", "PADRE"),
            ("tutor.supernovas@test.com", "tutor_supernovas", "Óscar", "Mendoza", "H", "Supernovas", "TUTOR"),
            ("tutor.meteors@test.com", "tutor_meteors", "Gabriela", "Salinas", "M", "Meteors", "PADRE"),
        ]
        for email, uname, first, last, gender, team_name, relation in guardian_data:
            g = self.get_or_create_user(
                email=email, username=uname, first=first, last=last,
                role_name="GUARDIAN", gender=gender, birth=datetime.date(1984, 6, 2),
            )
            team = teams[team_name]
            tutelados = []
            athletes = User.objects.filter(
                team_memberships__team=team,
                team_memberships__role_in_team="ATHLETE",
                team_memberships__is_active=True,
            ).order_by("pk")[:2]
            for a in athletes:
                if AthleteProfile.objects.filter(user=a).exists():
                    Guardianship.objects.update_or_create(
                        athlete=a, guardian=g, defaults={"relation": relation},
                    )
                    tutelados.append(a.get_full_name())
            self.guardians.append(g)
            self.record_user(g, "GUARDIAN",
                             f"{relation} — tutor de: {', '.join(tutelados) or 'sin asignar'}",
                             team=team_name)

        # Segundo tutor de las atletas de Comets: el caso que el modelo viejo
        # no podía representar, y el que hay que poder ver en la simulación.
        if self.guardians:
            segundo = self.get_or_create_user(
                email="tutor2.comets@test.com", username="tutor2_comets",
                first="Marcos", last="Cruz", role_name="GUARDIAN",
                gender="H", birth=datetime.date(1982, 9, 15),
            )
            for vinculo in Guardianship.objects.filter(guardian=self.guardians[0]):
                Guardianship.objects.update_or_create(
                    athlete=vinculo.athlete, guardian=segundo,
                    defaults={"relation": "PADRE"},
                )
            self.guardians.append(segundo)
            self.record_user(segundo, "GUARDIAN",
                             "Segundo tutor de las mismas atletas de Comets",
                             team="Comets")

        # ── Operarios: uno por rol de producción ─────────────────────
        from production.models import ProductionRole
        from production.services import OperarioService

        operario_data = [
            ("CONE", "operario.cone@test.com", "operario_cone", "Concepción", "Ibarra", "M"),
            ("SR. TINO", "operario.tino@test.com", "operario_tino", "Faustino", "Ramírez", "H"),
            ("DANI", "operario.dani@test.com", "operario_dani", "Daniela", "Ochoa", "M"),
            ("CHINO", "operario.chino@test.com", "operario_chino", "Joaquín", "Lara", "H"),
            ("SRA. CHIVIS", "operario.chivis@test.com", "operario_chivis", "Silvia", "Contreras", "M"),
            ("TERE", "operario.tere@test.com", "operario_tere", "Teresa", "Nava", "M"),
            ("MANUEL", "operario.manuel@test.com", "operario_manuel", "Manuel", "Zepeda", "H"),
        ]
        self.operarios = {}
        for role_name, email, uname, first, last, gender in operario_data:
            u = self.get_or_create_user(
                email=email, username=uname, first=first, last=last,
                role_name="OPERARIO", gender=gender, birth=datetime.date(1980, 4, 18),
            )
            prod_role = ProductionRole.objects.filter(name=role_name).first()
            stages_txt = ""
            if prod_role:
                OperarioService.assign_role(u, prod_role, self.admin)
                stages_txt = ", ".join(s.name for s in prod_role.stages.all())
            self.operarios[role_name] = u
            self.record_user(u, "OPERARIO",
                             f"Rol de producción {role_name} → etapas: {stages_txt or 'sin etapas'}")

        for name, team in teams.items():
            self.report["teams"].append({
                "name": team.name,
                "city": team.city,
                "join_code": team.join_code,
                "headcoach": team.coach.email,
                "coaches": list(
                    User.objects.filter(team_memberships__team=team,
                                        team_memberships__role_in_team="COACH")
                    .values_list("email", flat=True)
                ),
                "athletes": User.objects.filter(
                    team_memberships__team=team,
                    team_memberships__role_in_team="ATHLETE",
                    team_memberships__is_active=True,
                ).count(),
            })

    # ==================================================================
    # FASE 2 — CONFIGURACIÓN DE PRODUCCIÓN
    # ==================================================================
    def phase_production_config(self):
        from production.models import ProductionStage, ProductStageConfig
        from products.models import Product, ProductSizeVariant, Season

        stages = {s.slug: s for s in ProductionStage.objects.all()}

        # Ruta completa de manufactura (uniformes hechos en taller).
        FULL = [
            "seleccion-tallas", "planeacion-materiales", "control-surtido-materiales",
            "corte", "sublimacion", "costura", "calidad-costura",
            "cristaleria-plantillas", "calidad-aplicaciones", "calidad-final",
            "empaque", "envios",
        ]
        # Ruta corta: mercancía que solo se surte y se manda.
        SHORT = ["control-surtido-materiales", "calidad-final", "empaque", "envios"]

        routes = {
            "Uniforme Base": FULL,
            "Uniforme Personalizado por Equipo": FULL,
            "Uniforme Atleta Custom": FULL,
            "Shorts de Entrenamiento": FULL,
            "Tenis de Competencia": SHORT,
            "Mochila Space Cheer": SHORT,
            "Accesorio Porrista": SHORT,
        }

        for product_name, slugs in routes.items():
            product = Product.objects.filter(name=product_name).first()
            if not product:
                self.warn(f"producto no encontrado: {product_name}")
                continue
            for order_idx, slug in enumerate(slugs, start=1):
                stage = stages.get(slug)
                if not stage:
                    continue
                ProductStageConfig.objects.update_or_create(
                    product=product, stage=stage,
                    defaults={"display_order": order_idx},
                )
            self.info(f"{product_name}: {len(slugs)} etapas configuradas")

        season = Season.objects.filter(is_active=True).first()

        # Producto de talla por alumno: TEAM_CUSTOM + STANDARD es la única
        # combinación que activa `uses_standard_sizes`, y por lo tanto la
        # rejilla de tallas y la hoja imprimible del taller. Sin uno así, esas
        # dos pantallas quedan vacías (la hoja responde 404).
        self.playera, creada = Product.objects.get_or_create(
            name="Playera de Entrenamiento del Equipo",
            season=season,
            defaults={
                "description": "Playera con el escudo del equipo. Se reparte por talla entre las atletas.",
                "product_type": "UNIFORM",
                "usage_type": "TEAM_CUSTOM",
                "scope": "CATALOG",
                "size_strategy": "STANDARD",
                "base_price": Decimal("380.00"),
            },
        )
        for talla, extra in [("XS", "0.00"), ("S", "0.00"), ("M", "0.00"),
                             ("L", "40.00"), ("XL", "80.00")]:
            ProductSizeVariant.objects.get_or_create(
                product=self.playera, size=talla,
                defaults={"additional_price": Decimal(extra)},
            )
        for order_idx, slug in enumerate(FULL, start=1):
            stage = stages.get(slug)
            if stage:
                ProductStageConfig.objects.update_or_create(
                    product=self.playera, stage=stage,
                    defaults={"display_order": order_idx},
                )
        self.ok(f"Producto por talla {'creado' if creada else 'ya existía'}: {self.playera.name}")

        # Producto interno para pedidos offline (scope INTERNAL).
        self.internal_product, created = Product.objects.get_or_create(
            name="Uniforme Taller (captura offline)",
            season=season,
            defaults={
                "description": "Producto interno para capturar pedidos offline del taller.",
                "product_type": "UNIFORM",
                "usage_type": "GLOBAL",
                "scope": "INTERNAL",
                "size_strategy": "NONE",
                "base_price": Decimal("1500.00"),
            },
        )
        for order_idx, slug in enumerate(FULL, start=1):
            stage = stages.get(slug)
            if stage:
                ProductStageConfig.objects.update_or_create(
                    product=self.internal_product, stage=stage,
                    defaults={"display_order": order_idx},
                )
        self.ok(f"Producto interno {'creado' if created else 'ya existía'}: {self.internal_product.name}")

    # ==================================================================
    # FASE 3 — PEDIDOS
    # ==================================================================
    def phase_orders(self):
        from orders.models import Order, OrderDesignImage, OrderPayment, Customer
        from orders.services.factories import OrderContactInfoFactory
        from orders.services.servicesItems.order_item_athlete_service import OrderItemAthleteService
        from orders.services.servicesItems.order_item_service import OrderItemService
        from orders.services.state import OrderCreationService, OrderStateService
        from products.models import Product, ProductSizeVariant

        today = datetime.date.today()
        P = {p.name: p for p in Product.objects.all()}
        self.products = P
        self.orders = {}
        self.order_notes = {}

        def transition(order, to_status, user, notes="", **kw):
            # transition() relee la orden con
            # select_for_update y muta ESA instancia: la local queda con el
            # estado viejo si no la refrescamos.
            OrderStateService.transition(order, to_status, user, notes=notes, **kw)
            order.refresh_from_db()
            order.invalidate_cache()
            return order

        def build(team, creator, specs, label):
            """Crea un pedido TEAM en DRAFT con contacto, items y atletas."""
            order = OrderCreationService.create_order(
                order_type="TEAM", created_by=creator, owner_team=team,
            )
            contact = OrderContactInfoFactory.from_user(order, creator)
            contact.shipping_notes = f"Simulación: {label}"
            contact.save()

            for product, qty, size_name in specs:
                variant = None
                if size_name:
                    variant = ProductSizeVariant.objects.filter(
                        product=product, size=size_name
                    ).first()
                item = OrderItemService.add_product(order, product, quantity=qty, size_variant=variant)
                if product.requires_athletes:
                    OrderItemAthleteService.import_from_team(item)
            return order

        def set_dates(order, *, measures_days=10, delivery_days=45, freeze=True):
            order.measurements_due_date = today + datetime.timedelta(days=measures_days)
            order.uniform_delivery_date = today + datetime.timedelta(days=delivery_days)
            if freeze:
                order.freeze_payment_date = timezone.now()
            order.save(update_fields=[
                "measurements_due_date", "uniform_delivery_date", "freeze_payment_date",
            ])

        def lock_measures(order, user):
            """Bloqueo definitivo de medidas: paso manual del admin antes de
            liberar a taller (mismo servicio que usa measurement_views)."""
            from orders.services.measurements.MeasurementLifecycleService import (
                MeasurementLifecycleService,
            )
            order.refresh_from_db()
            if any(i.product.requires_measurements for i in order.items.select_related("product")):
                MeasurementLifecycleService.lock(order, user=user)
                order.refresh_from_db()

        def add_final_design(order, uploader):
            OrderDesignImage.objects.create(
                order=order,
                uploaded_by=uploader,
                is_final=True,
                image=ContentFile(PNG_1X1, name=f"diseno_final_orden_{order.pk}.png"),
            )

        def record(order, label, note):
            order.refresh_from_db()
            self.order_notes[label] = note
            entry = {
                "id": order.pk,
                "label": label,
                "type": order.order_type,
                "owner": str(order.owner),
                "status": order.status,
                "created_by": order.created_by.email,
                "total": str(order.total),
                "note": note,
                "items": [
                    {
                        "product": i.product.name,
                        "qty": i.quantity,
                        "size": i.size_variant.size if i.size_variant else "",
                        "athletes": i.athletes.count(),
                    }
                    for i in order.items.select_related("product", "size_variant")
                ],
            }
            self.report["orders"].append(entry)
            self.orders[label] = order
            self.ok(f"#{order.pk} {label} → {order.status}")

        custom = P["Uniforme Personalizado por Equipo"]
        mochila = P["Mochila Space Cheer"]
        tenis = P["Tenis de Competencia"]
        shorts = P["Shorts de Entrenamiento"]
        pompon = P["Accesorio Porrista"]
        base = P["Uniforme Base"]

        comets = self.teams["Comets"]
        supernovas = self.teams["Supernovas"]
        meteors = self.teams["Meteors"]

        # ── A. Comets — recorrido completo hasta DELIVERED ────────────
        a = build(comets, comets.coach, [(custom, 8, None), (mochila, 8, None)], "A-comets-entregado")
        set_dates(a)
        transition(a, "PENDING", user=comets.coach, notes="Enviado por el head coach")
        add_final_design(a, self.admin)
        transition(a, "DESIGN_APPROVED", user=comets.coach, notes="Diseño aprobado por el head coach")
        lock_measures(a, self.admin)
        a.first_payment_date = timezone.now()
        a.save(update_fields=["first_payment_date"])
        transition(a, "IN_PRODUCTION", user=self.admin, notes="Liberado a taller")
        record(a, "A-comets-entregado", "Se entrega al final de la fase 4, cuando su job cierra todas las etapas.")

        # ── B. Supernovas — en producción, avance parcial ─────────────
        b = build(supernovas, supernovas.coach, [(custom, 8, None), (tenis, 8, "25")], "B-supernovas-produccion")
        set_dates(b, delivery_days=30)
        transition(b, "PENDING", user=supernovas.coach)
        add_final_design(b, self.admin)
        transition(b, "DESIGN_APPROVED", user=self.admin, notes="Aprobado por administración")
        lock_measures(b, self.admin)
        b.first_payment_date = timezone.now()
        b.save(update_fields=["first_payment_date"])
        transition(b, "IN_PRODUCTION", user=self.admin)
        record(b, "B-supernovas-produccion", "Job en progreso: avanza hasta costura y ahí se queda.")

        # ── C. Meteors — urgente, apenas arrancando ───────────────────
        c = build(meteors, meteors.coach, [(custom, 8, None), (pompon, 16, None)], "C-meteors-urgente")
        set_dates(c, delivery_days=20)
        transition(c, "PENDING", user=meteors.coach)
        add_final_design(c, self.admin)
        transition(c, "DESIGN_APPROVED", user=meteors.coach)
        lock_measures(c, self.admin)
        c.first_payment_date = timezone.now()
        c.save(update_fields=["first_payment_date"])
        transition(c, "IN_PRODUCTION", user=self.admin, notes="Entra como urgente")
        record(c, "C-meteors-urgente", "Job marcado URGENTE. Solo pasó selección de tallas y planeación.")

        # ── D. Comets segundo pedido — job pausado ────────────────────
        d = build(comets, comets.coach, [(shorts, 8, "M")], "D-comets-pausado")
        set_dates(d, delivery_days=60, freeze=False)
        transition(d, "PENDING", user=comets.coach)
        d.first_payment_date = timezone.now()
        d.save(update_fields=["first_payment_date"])
        transition(d, "IN_PRODUCTION", user=self.admin, notes="Sin diseño: va directo a taller")
        record(d, "D-comets-pausado", "Producto sin diseño: PENDING → IN_PRODUCTION directo. El job se pausa por falta de material.")

        # ── E. Supernovas — esperando aprobación de diseño ────────────
        e = build(supernovas, supernovas.coach, [(custom, 8, None)], "E-supernovas-pendiente")
        set_dates(e, delivery_days=70)
        transition(e, "PENDING", user=supernovas.coach, notes="A la espera del arte final")
        record(e, "E-supernovas-pendiente", "PENDING sin diseño final subido. Es el pedido para probar la aprobación.")

        # ── F. Meteors — diseño aprobado, sin liberar a taller ─────────
        f = build(meteors, meteors.coach, [(custom, 8, None), (base, 8, "M")], "F-meteors-diseno-aprobado")
        set_dates(f, delivery_days=80)
        transition(f, "PENDING", user=meteors.coach)
        add_final_design(f, self.admin)
        transition(f, "DESIGN_APPROVED", user=meteors.coach)
        # Reparto de tallas por alumna sobre la playera del equipo: es lo que
        # llena la rejilla de tallas y la hoja imprimible del taller.
        from orders.services.servicesItems.size_assignment_service import (
            OrderItemSizeAssignmentService,
        )

        meteors_athletes = list(
            User.objects.filter(
                team_memberships__team=meteors,
                team_memberships__role_in_team="ATHLETE",
                team_memberships__is_active=True,
            ).order_by("pk")
        )
        reparto = ["S", "S", "M", "M", "M", "L", "L", "XL"]
        asignaciones = {
            atleta.id: reparto[idx % len(reparto)]
            for idx, atleta in enumerate(meteors_athletes)
        }
        OrderItemSizeAssignmentService.reconcile(
            f, self.playera, asignaciones, meteors.coach,
        )
        f.refresh_from_db()
        f.invalidate_cache()
        record(f, "F-meteors-diseno-aprobado",
               "DESIGN_APPROVED con medidas cerradas pero sin bloquear: falta el "
               "bloqueo y el primer pago para producción. Trae el reparto de "
               "tallas por alumna, así que su hoja imprimible tiene contenido.")

        # ── G. Comets — borrador sin terminar ─────────────────────────
        g = build(comets, comets.coach, [(mochila, 4, None)], "G-comets-borrador")
        record(g, "G-comets-borrador", "DRAFT editable. Sirve para probar agregar/quitar items y tallas.")

        # ── H. Supernovas — cancelado ─────────────────────────────────
        h = build(supernovas, supernovas.coach, [(tenis, 8, "24")], "H-supernovas-cancelado")
        set_dates(h, freeze=False)
        transition(h, "PENDING", user=supernovas.coach)
        transition(
            h, "CANCELLED", user=supernovas.coach,
            notes="El equipo cambió de proveedor de calzado",
        )
        record(h, "H-supernovas-cancelado", "CANCELLED desde PENDING con motivo registrado.")

        # ── I. Pedido PERSONAL de un atleta ───────────────────────────
        athlete = User.objects.filter(
            team_memberships__team=comets,
            team_memberships__role_in_team="ATHLETE",
        ).order_by("pk").first()
        i_order = OrderCreationService.create_order(
            order_type="PERSONAL", created_by=athlete, owner_user=athlete,
        )
        ci = OrderContactInfoFactory.from_user(i_order, athlete)
        ci.shipping_notes = "Simulación: pedido personal"
        ci.save()
        from orders.services.servicesItems.order_item_service import OrderItemService as OIS
        OIS.add_product(i_order, mochila, quantity=1)
        OIS.add_product(i_order, tenis, quantity=1,
                        size_variant=ProductSizeVariant.objects.filter(product=tenis, size="25").first())
        i_order.uniform_delivery_date = today + datetime.timedelta(days=25)
        i_order.first_payment_date = timezone.now()
        i_order.save(update_fields=["uniform_delivery_date", "first_payment_date"])
        transition(i_order, "PENDING", user=athlete)
        transition(i_order, "IN_PRODUCTION", user=self.admin)
        record(i_order, "I-personal-atleta", "Pedido PERSONAL de catálogo. Job corto (surtido→envíos), se entrega en la fase 4.")

        # ── J. Pedido OFFLINE con cliente externo y pagos ─────────────
        # Se captura con el servicio real de mostrador: crea el cliente, un
        # producto interno al vuelo desde la plantilla de producción y el
        # anticipo, y deja el pedido en PENDING.
        from orders.services.offline import OfflineOrderService
        from production.models import ProductionTemplate

        template = ProductionTemplate.objects.filter(name="Producción estándar").first()

        j = OfflineOrderService.create(
            admin_user=self.staff,
            customer_data={
                "name": "Academia Estelar A.C.",
                "phone": "3339998877",
                "email": "contacto@academiaestelar.mx",
                "notes": "Cliente externo capturado en mostrador",
            },
            items=[
                {
                    "product_id": self.internal_product.pk,
                    "quantity": 12,
                    "talla": "Mixta",
                    "notas": "6 tallas M y 6 tallas L, cuello redondo",
                },
                {
                    "new_product": {
                        "name": "Chamarra Academia Estelar",
                        "description": "Capturada al vuelo en el mostrador",
                        "product_type": "OTHER",
                        "base_price": "950.00",
                        "template_id": template.pk if template else None,
                    },
                    "quantity": 6,
                    "talla": "L",
                    "notas": "Bordado en espalda",
                },
            ],
            agreed_price=Decimal("21000.00"),
            delivery_date=today + datetime.timedelta(days=35),
            notes="Pedido de mostrador — Academia Estelar",
            initial_payment={"amount": Decimal("8000.00"), "method": "TRANSFER",
                             "notes": "Anticipo 38%"},
        )
        j.refresh_from_db()
        # Medidas capturadas a mano sobre el item interno (flujo offline).
        first_item = j.items.order_by("pk").first()
        OfflineOrderService.save_item_measurements(
            item=first_item,
            medidas={"pecho": "88", "cintura": "70", "estatura": "165"},
        )
        j.first_payment_date = timezone.now()
        j.save(update_fields=["first_payment_date"])
        j = transition(j, "IN_PRODUCTION", user=self.admin)
        record(j, "J-offline-academia",
               f"OFFLINE de mostrador. Acordado $21,000, anticipo $8,000, "
               f"saldo ${j.balance_due}. No se puede entregar hasta liquidar.")

    # ==================================================================
    # FASE 4 — PISO DE PRODUCCIÓN
    # ==================================================================
    def phase_production_floor(self):
        from production.models import (
            ErrorReport, OperarioRoleAssignment, ProductionJob, ProductionTask,
            StageResponsibility,
        )
        from production.services import ErrorReportService, ProductionJobService
        from production.state import ProductionJobStateService
        from orders.services.state import OrderStateService

        # Mapa etapa → operario responsable, vía StageResponsibility y roles.
        responsible_by_stage = {}
        for resp in StageResponsibility.objects.select_related("stage", "responsible_role"):
            assignment = OperarioRoleAssignment.objects.filter(
                role=resp.responsible_role
            ).select_related("user").first()
            if assignment:
                responsible_by_stage[resp.stage_id] = assignment.user

        def assign_all(job):
            """Asigna cada task al operario responsable de esa etapa."""
            assigned = 0
            for task in job.tasks.select_related("stage").all():
                operario = responsible_by_stage.get(task.stage_id)
                if operario:
                    ProductionJobService.assign_task(task, operario)
                    assigned += 1
            return assigned

        def advance(job, upto_slugs):
            """Completa, en orden de etapa, las tasks cuyas etapas están en la lista."""
            done = []
            tasks = job.tasks.select_related("stage", "order_item").order_by(
                "order_item_id", "stage__display_order"
            )
            for task in tasks:
                if task.stage.slug not in upto_slugs:
                    continue
                if task.status == ProductionTask.Status.COMPLETED:
                    continue
                worker = task.assigned_to or self.admin
                started = timezone.now() - datetime.timedelta(hours=3)
                ProductionJobService.complete_task(
                    task, worker, started,
                    notes=f"Completada en simulación por {worker.get_full_name()}",
                )
                done.append(task.stage.name)
            # complete_task transiciona su propia copia del job (select_for_update):
            # sin esto, nuestra instancia sigue creyendo que está en PENDING.
            job.refresh_from_db()
            return done

        def record_job(job, note):
            job.refresh_from_db()
            tasks = job.tasks.select_related("stage", "assigned_to", "completed_by", "order_item__product")
            self.report["production"].append({
                "job_id": job.pk,
                "order_id": job.order_id,
                "status": job.status,
                "is_urgent": job.is_urgent,
                "tasks_total": tasks.count(),
                "tasks_done": tasks.filter(status=ProductionTask.Status.COMPLETED).count(),
                "note": note,
                "assignments": [
                    {
                        "stage": t.stage.name,
                        "product": t.order_item.product.name,
                        "assigned_to": t.assigned_to.get_full_name() if t.assigned_to else "",
                        "status": t.status,
                        "completed_by": t.completed_by.get_full_name() if t.completed_by else "",
                    }
                    for t in tasks.order_by("order_item_id", "stage__display_order")
                ],
            })
            self.ok(f"Job #{job.pk} (orden #{job.order_id}) → {job.status} "
                    f"[{tasks.filter(status=ProductionTask.Status.COMPLETED).count()}/{tasks.count()} etapas]")

        FULL = ["seleccion-tallas", "planeacion-materiales", "control-surtido-materiales",
                "corte", "sublimacion", "costura", "calidad-costura",
                "cristaleria-plantillas", "calidad-aplicaciones", "calidad-final",
                "empaque", "envios"]

        jobs = {}
        for label, order in self.orders.items():
            job = ProductionJob.objects.filter(order=order).first()
            if job:
                jobs[label] = job
                assign_all(job)

        # ── A: se completa entero y la orden se entrega ───────────────
        job_a = jobs["A-comets-entregado"]
        advance(job_a, set(FULL))
        order_a = self.orders["A-comets-entregado"]
        order_a.refresh_from_db()
        order_a.final_payment_date = timezone.now()
        order_a.save(update_fields=["final_payment_date"])
        OrderStateService.transition(order_a, "DELIVERED", user=self.admin, notes="Entregado en sede del equipo")
        record_job(job_a, "Todas las etapas completadas. La orden pasó a DELIVERED y el job cerró en COMPLETED.")

        # ── B: avanza hasta costura ──────────────────────────────────
        job_b = jobs["B-supernovas-produccion"]
        advance(job_b, {"seleccion-tallas", "planeacion-materiales",
                        "control-surtido-materiales", "corte", "sublimacion", "costura"})
        record_job(job_b, "Frenado después de costura: calidad de costura es la siguiente pendiente (Tere).")

        # ── C: urgente, apenas dos etapas ────────────────────────────
        job_c = jobs["C-meteors-urgente"]
        ProductionJobService.toggle_urgent(job_c)
        advance(job_c, {"seleccion-tallas", "planeacion-materiales"})
        record_job(job_c, "URGENTE. Solo tallas y planeación; el corte está pendiente con Sr. Tino.")

        # ── D: una etapa y pausa administrativa ──────────────────────
        job_d = jobs["D-comets-pausado"]
        advance(job_d, {"seleccion-tallas"})
        ProductionJobStateService.transition(
            job_d, ProductionJob.Status.PAUSED, user=self.admin,
            notes="Pausado: falta tela para los shorts",
        )
        record_job(job_d, "PAUSADO por el admin. Ninguna etapa avanza mientras siga en pausa.")

        # ── I: pedido personal, ruta corta completa ──────────────────
        job_i = jobs["I-personal-atleta"]
        advance(job_i, set(FULL))
        order_i = self.orders["I-personal-atleta"]
        order_i.refresh_from_db()
        OrderStateService.transition(order_i, "DELIVERED", user=self.admin, notes="Entregado en recepción")
        record_job(job_i, "Ruta corta (surtido, calidad final, empaque, envíos) terminada. Orden entregada.")

        # ── J: offline en corte ──────────────────────────────────────
        job_j = jobs["J-offline-academia"]
        advance(job_j, {"seleccion-tallas", "planeacion-materiales",
                        "control-surtido-materiales", "corte"})
        record_job(job_j, "Pedido de mostrador en sublimación. No puede entregarse hasta liquidar el saldo.")

        # ── Reportes de error ────────────────────────────────────────
        from production.models import ProductionStage

        stage_corte = ProductionStage.objects.filter(slug="corte").first()
        stage_sub = ProductionStage.objects.filter(slug="sublimacion").first()
        stage_costura = ProductionStage.objects.filter(slug="costura").first()

        r1 = ErrorReportService.create(
            reported_by=self.operarios["TERE"],
            description="Dos tops salieron con la costura del hombro floja; se detectó en la revisión de calidad.",
            error_types=[ErrorReport.ErrorType.DEFECTIVE_SEWING],
            order=self.orders["B-supernovas-produccion"],
            job=jobs["B-supernovas-produccion"],
            stage=stage_costura,
            area="Costura",
            responsible=self.operarios["SRA. CHIVIS"],
            responsible_area="Costura",
            error_causes=[ErrorReport.ErrorCause.RUSH],
            cause_detail="Se apuró el cierre del lote para alcanzar el envío del viernes.",
            error_impacts=[ErrorReport.ErrorImpact.REDO_GARMENT, ErrorReport.ErrorImpact.DELIVERY_DELAY],
            impact_description="Dos prendas regresan a costura, un día de retraso.",
            corrective_actions="Se reprocesaron las dos prendas el mismo turno.",
            prevention_actions="Revisión intermedia cada 10 piezas en lotes urgentes.",
        )
        ErrorReportService.review(
            r1, self.admin, ErrorReport.ReviewStatus.REPOSITION_REQUIRED,
            review_notes="Se autoriza reposición de las dos prendas con cargo a taller.",
        )

        r2 = ErrorReportService.create(
            reported_by=self.operarios["DANI"],
            description="La sublimación del pedido urgente salió con el tono de azul dos puntos abajo del pantone del equipo.",
            error_types=[ErrorReport.ErrorType.WRONG_SUBLIMATION],
            order=self.orders["C-meteors-urgente"],
            job=jobs["C-meteors-urgente"],
            stage=stage_sub,
            area="Sublimación",
            responsible=self.operarios["CONE"],
            responsible_area="Sublimación",
            error_causes=[ErrorReport.ErrorCause.WRONG_INFO],
            cause_detail="El archivo de arte llegó en RGB en lugar de CMYK.",
            error_impacts=[ErrorReport.ErrorImpact.AFFECTS_QUALITY],
            impact_description="Diferencia de tono visible solo bajo luz directa.",
            corrective_actions="Se validó con el head coach y aceptó el tono.",
            prevention_actions="Checklist de perfil de color antes de mandar a plotter.",
        )
        ErrorReportService.review(
            r2, self.admin, ErrorReport.ReviewStatus.EXCEPTION_GRANTED,
            review_notes="El cliente aceptó la variación. No se repone.",
            is_exception=True,
            exception_reason="Aprobación explícita del head coach de Meteors.",
        )

        r3 = ErrorReportService.create(
            reported_by=self.operarios["SR. TINO"],
            description="Se cortaron 10 piezas con el molde de la talla anterior antes de detectar el cambio de medidas.",
            error_types=[ErrorReport.ErrorType.WRONG_CUT, ErrorReport.ErrorType.WASTED_MATERIAL
                         if hasattr(ErrorReport.ErrorType, "WASTED_MATERIAL")
                         else ErrorReport.ErrorType.WRONG_MATERIAL],
            order=self.orders["J-offline-academia"],
            job=jobs["J-offline-academia"],
            stage=stage_corte,
            area="Corte",
            responsible=self.operarios["SR. TINO"],
            responsible_area="Corte",
            error_causes=[ErrorReport.ErrorCause.LACK_OF_COMMUNICATION],
            cause_detail="El ajuste de medidas se avisó por teléfono y no se registró en el sistema.",
            error_impacts=[ErrorReport.ErrorImpact.WASTED_MATERIAL, ErrorReport.ErrorImpact.ADDITIONAL_COST],
            impact_description="Aproximadamente 6 metros de tela perdidos.",
            corrective_actions="Se recortó con el molde correcto y se reservó el sobrante para muestras.",
            prevention_actions="Todo cambio de medidas se captura en la orden antes de bajar a corte.",
        )

        for r in (r1, r2, r3):
            r.refresh_from_db()
            self.report["error_reports"].append({
                "id": r.pk,
                "order_id": r.order_id,
                "job_id": r.job_id,
                "stage": r.stage.name if r.stage else "",
                "reported_by": r.reported_by.get_full_name() if r.reported_by else "",
                "responsible": r.responsible.get_full_name() if r.responsible else "",
                "types": r.error_types,
                "review_status": r.review_status,
                "requires_reposition": r.requires_reposition,
                "reviewed_by": r.reviewed_by.get_full_name() if r.reviewed_by else "",
                "description": r.description,
            })
            self.ok(f"ErrorReport #{r.pk} orden #{r.order_id} → {r.review_status}")

    # ==================================================================
    # REPORTE DE ÓRDENES (se reconstruye tras la fase de producción)
    # ==================================================================
    def rebuild_orders_report(self):
        from orders.models import Order

        self.report["orders"] = []
        for label, order in self.orders.items():
            order = Order.objects.get(pk=order.pk)
            job = getattr(order, "production_job", None)
            self.report["orders"].append({
                "id": order.pk,
                "label": label,
                "type": order.order_type,
                "owner": str(order.owner),
                "status": order.status,
                "created_by": order.created_by.email,
                "total": str(order.total),
                "agreed_price": str(order.agreed_price) if order.agreed_price else "",
                "payment_status": order.payment_status,
                "measurements_open": order.measurements_open,
                "measurements_locked": order.measurements_locked,
                "measurements_due": order.measurements_due_date.isoformat() if order.measurements_due_date else "",
                "delivery_date": order.uniform_delivery_date.isoformat() if order.uniform_delivery_date else "",
                "job_id": job.pk if job else None,
                "job_status": job.status if job else "",
                "note": self.order_notes.get(label, ""),
                "items": [
                    {
                        "product": i.product.name,
                        "qty": i.quantity,
                        "size": i.size_variant.size if i.size_variant else "",
                        "athletes": i.athletes.count(),
                        "unit_price": str(i.unit_price),
                    }
                    for i in order.items.select_related("product", "size_variant")
                ],
                "log": [
                    f"{l.from_status or '—'} → {l.to_status} ({l.user.email if l.user else 'sistema'})"
                    for l in order.orderlog_set.order_by("created_at")
                ] if hasattr(order, "orderlog_set") else [],
            })
        self.ok(f"Reporte de órdenes reconstruido: {len(self.report['orders'])} pedidos")

    # ==================================================================
    # FASE 5 — EVENTOS, JUZGAMIENTO Y RESULTADOS
    # ==================================================================
    def phase_events(self):
        from events.models import (
            Event, EventCategory, EventJudgingCriteria, EventParticipant, EventResult,
            EventScore, EventStaffAssignment, EventStaffRole, EventTeamRegistration,
        )
        from teams.models import TeamCategory, UserTeamMembership

        today = datetime.date.today()

        judge_role, _ = EventStaffRole.objects.get_or_create(
            name="Juez de panel",
            defaults={"is_judge": True, "description": "Califica rutinas por criterio"},
        )
        coord_role, _ = EventStaffRole.objects.get_or_create(
            name="Coordinador de piso",
            defaults={"description": "Ordena entradas y salidas de tarima"},
        )

        def inscribir_equipos(event, category, status=EventTeamRegistration.STATUS_ACCEPTED):
            regs = {}
            for name, team in self.teams.items():
                reg, _ = EventTeamRegistration.objects.get_or_create(
                    event=event, team=team,
                    defaults={
                        "category": category,
                        "status": status,
                        "registered_by": team.coach,
                        "notes": "Inscripción de simulación",
                    },
                )
                regs[name] = reg
            return regs

        def registrar_participantes(event, regs):
            total = 0
            for name, team in self.teams.items():
                reg = regs[name]
                EventParticipant.objects.get_or_create(
                    event=event, user=team.coach,
                    defaults={
                        "role": EventParticipant.ROLE_HEADCOACH,
                        "team_registration": reg,
                        "status": EventParticipant.STATUS_CONFIRMED,
                    },
                )
                total += 1
                memberships = UserTeamMembership.objects.filter(
                    team=team, is_active=True, status="accepted",
                ).select_related("user")
                for m in memberships:
                    if m.user_id == team.coach_id:
                        continue
                    role = (EventParticipant.ROLE_ATHLETE if m.role_in_team == "ATHLETE"
                            else EventParticipant.ROLE_COACH)
                    EventParticipant.objects.get_or_create(
                        event=event, user=m.user,
                        defaults={
                            "role": role,
                            "team_registration": reg,
                            "status": EventParticipant.STATUS_CONFIRMED,
                        },
                    )
                    total += 1
            return total

        def asignar_staff(event):
            for judge in self.judges:
                EventStaffAssignment.objects.get_or_create(
                    event=event, user=judge, role=judge_role,
                    defaults={"assigned_by": self.admin, "notes": "Panel principal"},
                )
            EventStaffAssignment.objects.get_or_create(
                event=event, user=self.staff, role=coord_role,
                defaults={"assigned_by": self.admin},
            )

        # -- Evento 1: Grand Prix — inscripciones abiertas, aun sin juzgar --
        gp = Event.objects.filter(name__startswith="Grand Prix").first()
        if gp:
            category = gp.categories.order_by("order").first()
            regs = inscribir_equipos(gp, category)
            asignar_staff(gp)
            registrar_participantes(gp, regs)
            for g in self.guardians:
                EventParticipant.objects.get_or_create(
                    event=gp, user=g,
                    defaults={
                        "role": EventParticipant.ROLE_GUARDIAN,
                        "team_registration": regs["Comets"],
                        "status": EventParticipant.STATUS_REGISTERED,
                    },
                )
            self.gp = gp
            self.ok(f"Grand Prix: {gp.team_registrations.count()} equipos inscritos, "
                    f"{gp.participants.count()} participantes, panel de {len(self.judges)} jueces")
        else:
            self.gp = None
            self.warn("No se encontró el Grand Prix")

        # -- Evento 2: Copa Nebulosa — competencia juzgada de punta a punta --
        nebulosa = Event.objects.filter(name="Copa Nebulosa — SIMULACIÓN").first()
        if nebulosa is None:
            nebulosa = Event(
                name="Copa Nebulosa — SIMULACIÓN",
                description=(
                    "Competencia cerrada con panel de 3 jueces, 4 criterios ponderados "
                    "y resultados publicados. Generada por simulate_platform."
                ),
                event_type=Event.TYPE_COMPETITION,
                status=Event.STATUS_COMPLETED,
                organizer=self.admin,
                venue_name="Domo Nebulosa",
                venue_address="Circuito Estelar 77",
                venue_city="Querétaro",
                start_date=today - datetime.timedelta(days=21),
                end_date=today - datetime.timedelta(days=20),
                registration_open=today - datetime.timedelta(days=90),
                registration_close=today - datetime.timedelta(days=30),
                max_teams=12,
            )
            nebulosa.save()
            self.ok(f"Evento CREADO: {nebulosa.name}")

        team_cat = TeamCategory.objects.filter(name__icontains="Nivel 2").first()
        cat_neb, _ = EventCategory.objects.get_or_create(
            event=nebulosa, name="Senior Nivel 2",
            defaults={
                "team_category": team_cat,
                "max_teams": 8,
                "description": "Categoría única de la Copa Nebulosa",
                "order": 1,
            },
        )

        criteria_cfg = [
            ("Técnica", "Ejecución limpia de stunts y tumbling", 30, Decimal("30.00"), 1),
            ("Sincronización", "Precisión del equipo como unidad", 25, Decimal("25.00"), 2),
            ("Dificultad", "Nivel de riesgo y complejidad de la rutina", 25, Decimal("25.00"), 3),
            ("Presentación", "Uniformes, formación, energía y actitud", 20, Decimal("20.00"), 4),
        ]
        criteria = {}
        for cname, desc, weight, max_score, order in criteria_cfg:
            c, _ = EventJudgingCriteria.objects.get_or_create(
                event=nebulosa, name=cname,
                defaults={
                    "description": desc, "weight": weight,
                    "max_score": max_score, "order": order, "is_active": True,
                },
            )
            criteria[cname] = c

        asignar_staff(nebulosa)
        regs_neb = inscribir_equipos(nebulosa, cat_neb)
        registrar_participantes(nebulosa, regs_neb)

        # Cada juez califica a cada equipo en cada criterio. Los tres jueces
        # difieren un poco entre si — es lo que hace util promediar.
        base_scores = {
            "Comets":     {"Técnica": 27.5, "Sincronización": 23.0, "Dificultad": 22.5, "Presentación": 18.5},
            "Supernovas": {"Técnica": 25.0, "Sincronización": 22.0, "Dificultad": 23.5, "Presentación": 17.0},
            "Meteors":    {"Técnica": 24.0, "Sincronización": 20.5, "Dificultad": 20.0, "Presentación": 18.0},
        }
        judge_bias = [Decimal("0.0"), Decimal("-0.75"), Decimal("0.5")]

        totals = {}
        for team_name, per_criteria in base_scores.items():
            reg = regs_neb[team_name]
            team_total = Decimal("0.00")
            for cname, base in per_criteria.items():
                crit = criteria[cname]
                judge_scores = []
                for idx, judge in enumerate(self.judges):
                    value = Decimal(str(base)) + judge_bias[idx % len(judge_bias)]
                    value = max(Decimal("0.00"), min(value, crit.max_score))
                    EventScore.objects.get_or_create(
                        team_registration=reg, criteria=crit, judge=judge,
                        round=EventScore.ROUND_FINAL,
                        defaults={"score": value, "notes": f"Panel — {judge.get_full_name()}"},
                    )
                    judge_scores.append(value)
                promedio = sum(judge_scores) / len(judge_scores)
                team_total += promedio
            totals[team_name] = team_total.quantize(Decimal("0.01"))

        ranking = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
        for placement, (team_name, total) in enumerate(ranking, start=1):
            EventResult.objects.update_or_create(
                team_registration=regs_neb[team_name],
                category=cat_neb,
                round=EventResult.ROUND_FINAL,
                defaults={
                    "placement": placement,
                    "total_score": total,
                    "published": True,
                    "published_at": timezone.now(),
                    "notes": "Promedio de los 3 jueces por criterio",
                },
            )
            self.ok(f"Copa Nebulosa — {placement}o {team_name}: {total} pts")

        self.nebulosa = nebulosa

        # -- Volcado al reporte --
        for event in Event.objects.all().order_by("start_date"):
            self.report["events"].append({
                "id": event.pk,
                "name": event.name,
                "status": event.status,
                "type": event.event_type,
                "venue": f"{event.venue_name}, {event.venue_city}",
                "start": event.start_date.isoformat(),
                "end": event.end_date.isoformat(),
                "teams": event.team_registrations.count(),
                "participants": event.participants.count(),
                "judges": [
                    a.user.get_full_name()
                    for a in event.staff_assignments.filter(role__is_judge=True).select_related("user")
                ],
                "criteria": [
                    {"name": c.name, "weight": str(c.weight), "max": str(c.max_score)}
                    for c in event.judging_criteria.all()
                ],
                "scores": EventScore.objects.filter(team_registration__event=event).count(),
                "results": [
                    {
                        "placement": r.placement,
                        "team": r.team_registration.team.name,
                        "score": str(r.total_score),
                        "published": r.published,
                    }
                    for r in EventResult.objects.filter(team_registration__event=event)
                    .select_related("team_registration__team").order_by("placement")
                ],
            })

    # ==================================================================
    # FASE 6 — HOSPITALIDAD
    # ==================================================================
    def phase_hospitality(self):
        from hospitality.models import (
            Bed, BedAssignment, Hotel, HospitalityPreference, Room, RoomAssignment,
            RoomFeature, RoomType, Stay,
        )
        from events.models import EventParticipant

        event = getattr(self, "gp", None)
        if event is None:
            self.warn("Sin evento base — se omite hospitalidad")
            return

        hotel, _ = Hotel.objects.get_or_create(
            event=event, name="Hotel Órbita Centro",
            defaults={
                "address": "Av. Cosmos 480",
                "city": event.venue_city or "Ciudad de México",
                "phone": "5544332211",
                "description": "Bloque reservado para los equipos del Grand Prix.",
            },
        )

        room_type, _ = RoomType.objects.get_or_create(
            hotel=hotel, name="Cuádruple estándar",
            defaults={
                "capacity": 4,
                "description": "Dos camas matrimoniales, ideal para atletas.",
                "base_price": Decimal("1850.00"),
            },
        )
        features = list(RoomFeature.objects.all()[:4])
        if features:
            room_type.features.set(features)

        coach_type, _ = RoomType.objects.get_or_create(
            hotel=hotel, name="Triple staff",
            defaults={
                "capacity": 3,
                "description": "Habitación para cuerpo técnico (3 head coaches).",
                "base_price": Decimal("1400.00"),
            },
        )

        check_in = event.start_date - datetime.timedelta(days=1)
        check_out = event.end_date + datetime.timedelta(days=1)

        rooms = {}
        for idx, team_name in enumerate(self.teams.keys(), start=1):
            room, _ = Room.objects.get_or_create(
                hotel=hotel, room_number=f"{200 + idx}", floor=2,
                defaults={"room_type": room_type, "notes": f"Bloque de {team_name}"},
            )
            # Una cama por plaza: la capacidad del tipo de habitación manda.
            camas = (("Cama A", Bed.DOUBLE), ("Cama B", Bed.DOUBLE),
                     ("Cama C", Bed.SINGLE), ("Cama D", Bed.SINGLE))
            for label, bed_type in camas[: room_type.capacity]:
                Bed.objects.get_or_create(
                    room=room, label=label, defaults={"bed_type": bed_type},
                )
            rooms[team_name] = room

        staff_room, _ = Room.objects.get_or_create(
            hotel=hotel, room_number="301", floor=3,
            defaults={"room_type": coach_type, "notes": "Cuerpo técnico"},
        )
        for label in ("Cama A", "Cama B", "Cama C")[: coach_type.capacity]:
            Bed.objects.get_or_create(room=staff_room, label=label,
                                      defaults={"bed_type": Bed.QUEEN})

        def crear_estancia(user, room, status=Stay.CONFIRMED, notes="", bed=None):
            participant = EventParticipant.objects.filter(event=event, user=user).first()
            stay, _ = Stay.objects.get_or_create(
                event=event, user=user,
                defaults={
                    "event_participant": participant,
                    "hotel": hotel,
                    "check_in_date": check_in,
                    "check_out_date": check_out,
                    "status": status,
                    "notes": notes,
                    "created_by": self.staff,
                },
            )
            if hasattr(stay, "room_assignment"):
                return stay, stay.room_assignment
            ocupadas = (
                RoomAssignment.objects.filter(room=room)
                .exclude(stay__status=Stay.CANCELLED)
                .count()
            )
            if ocupadas >= room.room_type.capacity:
                return stay, None
            ra = RoomAssignment.objects.create(
                stay=stay, room=room, assigned_by=self.staff,
                notes=notes or "Asignación de simulación",
            )
            elegida = bed
            if elegida is None:
                # Primera cama con lugar libre: una cama admite tantas personas
                # como su capacidad efectiva, no necesariamente una.
                for candidata in room.beds.order_by("pk"):
                    ocupada = BedAssignment.objects.filter(bed=candidata).count()
                    if ocupada < candidata.effective_capacity:
                        elegida = candidata
                        break
            if elegida is not None:
                BedAssignment.objects.get_or_create(
                    stay=stay, bed=elegida,
                    defaults={"assigned_by": self.staff},
                )
            return stay, ra

        # ── Habitación familiar: una tutora viaja con sus dos atletas y
        # comparte cama matrimonial con una de ellas para abaratar el viaje.
        # Es el caso que la regla de capacidad de cama vino a habilitar.
        familia_type, _ = RoomType.objects.get_or_create(
            hotel=hotel, name="Familiar",
            defaults={
                "capacity": 3,
                "description": "Para un tutor que viaja con sus atletas.",
                "base_price": Decimal("2100.00"),
            },
        )
        familia_room, _ = Room.objects.get_or_create(
            hotel=hotel, room_number="204", floor=2,
            defaults={"room_type": familia_type, "notes": "Tutora + atletas a su cargo"},
        )
        cama_matrimonial, _ = Bed.objects.get_or_create(
            room=familia_room, label="Cama matrimonial",
            defaults={"bed_type": Bed.DOUBLE},
        )
        Bed.objects.get_or_create(
            room=familia_room, label="Cama individual",
            defaults={"bed_type": Bed.SINGLE},
        )

        tutora = self.guardians[0]  # tutora de Comets
        a_cargo = list(
            User.objects.filter(guardianships__guardian=tutora).order_by("pk")[:2]
        )
        ya_alojados = set()
        if a_cargo:
            crear_estancia(tutora, familia_room, notes="Tutora — viaja con sus atletas",
                           bed=cama_matrimonial)
            crear_estancia(a_cargo[0], familia_room, bed=cama_matrimonial,
                           notes="Comparte cama con su tutora")
            ya_alojados.add(a_cargo[0].pk)
            if len(a_cargo) > 1:
                crear_estancia(a_cargo[1], familia_room, notes="Atleta a cargo de la tutora")
                ya_alojados.add(a_cargo[1].pk)
            self.report["hospitality"].append({
                "hotel": hotel.name,
                "room": familia_room.room_number,
                "room_type": familia_type.name,
                "capacity": familia_type.capacity,
                "team": "Comets (familiar)",
                "check_in": check_in.isoformat(),
                "check_out": check_out.isoformat(),
                "occupants": [tutora.get_full_name()] + [a.get_full_name() for a in a_cargo],
                "headcoach_room": staff_room.room_number,
                "nota": (f"{tutora.get_full_name()} comparte la cama matrimonial con "
                         f"{a_cargo[0].get_full_name()}: permitido por ser su tutora."),
            })

        total_stays = 0
        for team_name, team in self.teams.items():
            room = rooms[team_name]
            athletes = list(
                User.objects.filter(
                    team_memberships__team=team,
                    team_memberships__role_in_team="ATHLETE",
                    team_memberships__is_active=True,
                ).exclude(pk__in=ya_alojados).order_by("pk")[: room.room_type.capacity]
            )
            asignados = []
            for athlete in athletes:
                stay, ra = crear_estancia(athlete, room, notes=f"Atleta {team_name}")
                if ra:
                    asignados.append(athlete.get_full_name())
                total_stays += 1

            # El head coach duerme en la habitacion de staff.
            crear_estancia(team.coach, staff_room, notes=f"Head coach {team_name}")
            total_stays += 1

            # Preferencias de hospedaje del head coach.
            pref, _ = HospitalityPreference.objects.get_or_create(
                event=event, user=team.coach,
                defaults={
                    "preferred_hotel": hotel,
                    "preferred_room_type": coach_type,
                    "special_needs": "Piso alto, lejos del elevador",
                    "notes": "Preferencia registrada en la simulación",
                },
            )
            if features:
                pref.preferred_features.set(features[:2])

            self.report["hospitality"].append({
                "hotel": hotel.name,
                "room": room.room_number,
                "room_type": room.room_type.name,
                "capacity": room.room_type.capacity,
                "team": team_name,
                "check_in": check_in.isoformat(),
                "check_out": check_out.isoformat(),
                "occupants": asignados,
                "headcoach_room": staff_room.room_number,
            })

        self.ok(f"{hotel.name}: {Room.objects.filter(hotel=hotel).count()} habitaciones, "
                f"{Stay.objects.filter(event=event).count()} estancias, "
                f"{BedAssignment.objects.filter(bed__room__hotel=hotel).count()} camas asignadas")
