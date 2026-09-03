"""
Reglas de alojamiento: capacidad real de cada cama y convivencia de menores.

Dos reglas de negocio:
  1. Una cama admite tantos huéspedes como su capacidad. El tipo de cama da el
     default (individual 1, el resto 2) y cada cama puede sobrescribirlo.
  2. Un menor de edad solo comparte habitación o cama con alguno de sus tutores
     acreditados o con adultos acreditados de su equipo (coaches y staff).
"""

import datetime

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import AthleteProfile, Role
from custody.models import Guardianship
from events.models import Event
from hospitality.models import (
    Bed, BedAssignment, Hotel, Room, RoomAssignment, RoomType, Stay,
)
from hospitality.services import RoomAssignmentService
from orders.tests.factories import UserFactory
from teams.models import Team, UserTeamMembership


class LodgingTestBase(TestCase):
    """Evento con hotel, una habitación amplia y camas de varios tipos."""

    def setUp(self):
        self.today = datetime.date.today()

        self.admin = UserFactory(username="admin_lodging")
        self.event = Event.objects.create(
            name="Copa de Prueba",
            organizer=self.admin,
            start_date=self.today + datetime.timedelta(days=30),
            end_date=self.today + datetime.timedelta(days=31),
            venue_city="Guadalajara",
        )
        self.hotel = Hotel.objects.create(event=self.event, name="Hotel Prueba")
        self.room_type = RoomType.objects.create(
            hotel=self.hotel, name="Familiar", capacity=6,
        )
        self.room = Room.objects.create(
            hotel=self.hotel, room_type=self.room_type, room_number="101", floor=1,
        )

    # ── helpers ──────────────────────────────────────────────────────────
    def make_bed(self, bed_type=Bed.SINGLE, label="Cama A", capacity=None):
        return Bed.objects.create(
            room=self.room, bed_type=bed_type, label=label, capacity=capacity,
        )

    def make_user(self, *, age, username):
        """Usuario con la edad pedida (en años cumplidos)."""
        birth = self.today - datetime.timedelta(days=365 * age + 10)
        return UserFactory(username=username, birth_date=birth)

    def make_stay(self, user):
        return Stay.objects.create(
            event=self.event, user=user, hotel=self.hotel,
            check_in_date=self.event.start_date,
            check_out_date=self.event.end_date,
            status=Stay.CONFIRMED, created_by=self.admin,
        )

    def assign_room(self, user, room=None):
        stay = self.make_stay(user)
        return RoomAssignment.objects.create(
            stay=stay, room=room or self.room, assigned_by=self.admin,
        )

    def make_team(self, name="Equipo Prueba"):
        coach = self.make_user(age=35, username=f"coach_{name.lower().replace(' ', '_')}")
        return Team.objects.create(
            name=name, coach=coach, city="Guadalajara", phone="3312345678",
        ), coach

    def join_team(self, user, team, role_in_team="ATHLETE"):
        return UserTeamMembership.objects.create(
            user=user, team=team, role_in_team=role_in_team,
            status="accepted", is_active=True,
        )


# =====================================================================
# 1. CAPACIDAD DE CAMA
# =====================================================================

class BedCapacityTests(LodgingTestBase):

    def test_cama_individual_admite_un_solo_huesped(self):
        bed = self.make_bed(Bed.SINGLE)
        self.assertEqual(bed.effective_capacity, 1)

        primero = self.assign_room(self.make_user(age=30, username="h1"))
        BedAssignment.objects.create(stay=primero.stay, bed=bed)

        segundo = self.assign_room(self.make_user(age=31, username="h2"))
        with self.assertRaises(ValidationError):
            BedAssignment.objects.create(stay=segundo.stay, bed=bed)

    def test_cama_matrimonial_admite_dos_por_defecto(self):
        """El caso real: madre e hijo comparten cama para abaratar el viaje."""
        bed = self.make_bed(Bed.DOUBLE)
        self.assertEqual(bed.effective_capacity, 2)

        team, _ = self.make_team()
        madre = self.make_user(age=40, username="madre")
        hijo = self.make_user(age=14, username="hijo")
        self.join_team(hijo, team)
        AthleteProfile.objects.create(user=hijo, emergency_contact="Madre")
        Guardianship.objects.create(athlete=hijo, guardian=madre)

        ra_madre = self.assign_room(madre)
        ra_hijo = self.assign_room(hijo)
        BedAssignment.objects.create(stay=ra_madre.stay, bed=bed)
        BedAssignment.objects.create(stay=ra_hijo.stay, bed=bed)

        self.assertEqual(bed.assignments.count(), 2)

    def test_cama_matrimonial_rechaza_al_tercero(self):
        bed = self.make_bed(Bed.DOUBLE)
        for i in range(2):
            ra = self.assign_room(self.make_user(age=30 + i, username=f"a{i}"))
            BedAssignment.objects.create(stay=ra.stay, bed=bed)

        tercero = self.assign_room(self.make_user(age=33, username="tercero"))
        with self.assertRaises(ValidationError):
            BedAssignment.objects.create(stay=tercero.stay, bed=bed)

    def test_litera_admite_dos_por_defecto(self):
        self.assertEqual(self.make_bed(Bed.BUNK, label="L").effective_capacity, 2)

    def test_capacidad_explicita_manda_sobre_el_tipo(self):
        """Una individual declarada para 2 admite 2; el default no manda."""
        bed = self.make_bed(Bed.SINGLE, capacity=2)
        self.assertEqual(bed.effective_capacity, 2)

        for i in range(2):
            ra = self.assign_room(self.make_user(age=30 + i, username=f"c{i}"))
            BedAssignment.objects.create(stay=ra.stay, bed=bed)
        self.assertEqual(bed.assignments.count(), 2)

    def test_capacidad_explicita_puede_reducir_el_default(self):
        """Una matrimonial angosta se puede declarar para una sola persona."""
        bed = self.make_bed(Bed.DOUBLE, capacity=1)
        self.assertEqual(bed.effective_capacity, 1)

        ra = self.assign_room(self.make_user(age=30, username="solo"))
        BedAssignment.objects.create(stay=ra.stay, bed=bed)

        otro = self.assign_room(self.make_user(age=31, username="otro"))
        with self.assertRaises(ValidationError):
            BedAssignment.objects.create(stay=otro.stay, bed=bed)

    def test_capacidad_cero_es_invalida(self):
        with self.assertRaises(ValidationError):
            self.make_bed(Bed.SINGLE, capacity=0)

    def test_no_se_puede_reducir_capacidad_por_debajo_de_los_ocupantes(self):
        bed = self.make_bed(Bed.DOUBLE)
        for i in range(2):
            ra = self.assign_room(self.make_user(age=30 + i, username=f"d{i}"))
            BedAssignment.objects.create(stay=ra.stay, bed=bed)

        bed.capacity = 1
        with self.assertRaises(ValidationError):
            bed.save()

    def test_una_estancia_cancelada_libera_lugar(self):
        bed = self.make_bed(Bed.SINGLE)
        ra = self.assign_room(self.make_user(age=30, username="cancela"))
        BedAssignment.objects.create(stay=ra.stay, bed=bed)
        ra.stay.status = Stay.CANCELLED
        ra.stay.save()

        nuevo = self.assign_room(self.make_user(age=31, username="entra"))
        BedAssignment.objects.create(stay=nuevo.stay, bed=bed)  # no debe reventar

    def test_el_servicio_respeta_la_capacidad(self):
        bed = self.make_bed(Bed.DOUBLE)
        stays = []
        for i in range(3):
            ra = self.assign_room(self.make_user(age=30 + i, username=f"s{i}"))
            stays.append(ra.stay)

        RoomAssignmentService.assign_bed(stay=stays[0], bed=bed, assigned_by=self.admin)
        RoomAssignmentService.assign_bed(stay=stays[1], bed=bed, assigned_by=self.admin)
        with self.assertRaises(ValidationError):
            RoomAssignmentService.assign_bed(stay=stays[2], bed=bed, assigned_by=self.admin)


# =====================================================================
# 2. CONVIVENCIA DE MENORES
# =====================================================================

class MinorLodgingPolicyTests(LodgingTestBase):

    def setUp(self):
        super().setUp()
        self.team, self.coach = self.make_team("Cometas")
        self.menor = self.make_user(age=15, username="menor")
        self.join_team(self.menor, self.team)
        self.guardian = self.make_user(age=42, username="guardian")
        AthleteProfile.objects.create(
            user=self.menor, emergency_contact="Familia",
        )
        Guardianship.objects.create(athlete=self.menor, guardian=self.guardian)

    def test_menor_no_puede_compartir_habitacion_con_adulto_ajeno(self):
        ajeno = self.make_user(age=38, username="ajeno")
        self.assign_room(self.menor)
        with self.assertRaises(ValidationError):
            self.assign_room(ajeno)

    def test_orden_inverso_tambien_se_rechaza(self):
        """El adulto ajeno entra primero y el menor después."""
        ajeno = self.make_user(age=38, username="ajeno2")
        self.assign_room(ajeno)
        with self.assertRaises(ValidationError):
            self.assign_room(self.menor)

    def test_menor_puede_compartir_habitacion_con_su_guardian(self):
        self.assign_room(self.menor)
        self.assign_room(self.guardian)
        self.assertEqual(self.room.assignments.count(), 2)

    def test_menor_puede_compartir_habitacion_con_coach_de_su_equipo(self):
        self.assign_room(self.menor)
        self.assign_room(self.coach)
        self.assertEqual(self.room.assignments.count(), 2)

    def test_menor_puede_compartir_habitacion_con_staff_de_su_equipo(self):
        staff = self.make_user(age=29, username="staff_equipo")
        self.join_team(staff, self.team, role_in_team="STAFF")
        self.assign_room(self.menor)
        self.assign_room(staff)
        self.assertEqual(self.room.assignments.count(), 2)

    def test_coach_de_otro_equipo_no_cuenta(self):
        otro_team, otro_coach = self.make_team("Meteoros")
        self.assign_room(self.menor)
        with self.assertRaises(ValidationError):
            self.assign_room(otro_coach)

    def test_dos_menores_del_mismo_equipo_pueden_compartir(self):
        otra_menor = self.make_user(age=14, username="menor2")
        self.join_team(otra_menor, self.team)
        AthleteProfile.objects.create(
            user=otra_menor, emergency_contact="Familia",
        )
        Guardianship.objects.create(athlete=otra_menor, guardian=self.guardian)
        self.assign_room(self.menor)
        self.assign_room(otra_menor)
        self.assertEqual(self.room.assignments.count(), 2)

    def test_adultos_entre_si_no_tienen_restriccion(self):
        a = self.make_user(age=30, username="adulto_a")
        b = self.make_user(age=45, username="adulto_b")
        self.assign_room(a)
        self.assign_room(b)
        self.assertEqual(self.room.assignments.count(), 2)

    def test_menor_no_puede_compartir_cama_con_adulto_ajeno(self):
        """La habitación puede ser válida y la cama no: el coach acreditado
        puede dormir en el cuarto, pero no en la misma cama que la atleta."""
        bed = self.make_bed(Bed.DOUBLE)
        ra_menor = self.assign_room(self.menor)
        ra_coach = self.assign_room(self.coach)
        BedAssignment.objects.create(stay=ra_menor.stay, bed=bed)
        with self.assertRaises(ValidationError):
            BedAssignment.objects.create(stay=ra_coach.stay, bed=bed)

    def test_menor_si_puede_compartir_cama_con_su_guardian(self):
        bed = self.make_bed(Bed.DOUBLE)
        ra_menor = self.assign_room(self.menor)
        ra_guardian = self.assign_room(self.guardian)
        BedAssignment.objects.create(stay=ra_menor.stay, bed=bed)
        BedAssignment.objects.create(stay=ra_guardian.stay, bed=bed)
        self.assertEqual(bed.assignments.count(), 2)

    def test_el_servicio_rechaza_la_habitacion_con_adulto_ajeno(self):
        ajeno = self.make_user(age=38, username="ajeno3")
        self.assign_room(self.menor)
        stay = self.make_stay(ajeno)
        with self.assertRaises(ValidationError):
            RoomAssignmentService.assign_room(
                stay=stay, room=self.room, assigned_by=self.admin,
            )

    def test_estancia_cancelada_no_bloquea(self):
        ajeno = self.make_user(age=38, username="ajeno4")
        ra = self.assign_room(ajeno)
        ra.stay.status = Stay.CANCELLED
        ra.stay.save()
        self.assign_room(self.menor)  # no debe reventar

    # ── varios tutores ───────────────────────────────────────────────
    def _segundo_tutor(self, username="segundo_tutor"):
        otro = self.make_user(age=44, username=username)
        Guardianship.objects.create(athlete=self.menor, guardian=otro)
        return otro

    def test_el_segundo_tutor_puede_compartir_habitacion(self):
        """Criterio 4 de la spec."""
        padre = self._segundo_tutor("padre_hab")
        self.assign_room(self.menor)
        self.assign_room(padre)
        self.assertEqual(self.room.assignments.count(), 2)

    def test_el_segundo_tutor_puede_compartir_cama(self):
        """Criterio 3: hoy esto era ValidationError."""
        padre = self._segundo_tutor("padre_cama")
        bed = self.make_bed(Bed.DOUBLE)
        ra_menor = self.assign_room(self.menor)
        ra_padre = self.assign_room(padre)
        BedAssignment.objects.create(stay=ra_menor.stay, bed=bed)
        BedAssignment.objects.create(stay=ra_padre.stay, bed=bed)
        self.assertEqual(bed.assignments.count(), 2)

    def test_los_tres_tipos_de_relacion_valen_para_la_cama(self):
        """El criterio de cama no distingue PADRE / TUTOR / ACOMP."""
        from hospitality.policies import MinorLodgingPolicy

        for i, relacion in enumerate(
            (Guardianship.PADRE, Guardianship.TUTOR, Guardianship.ACOMP)
        ):
            tutor = self.make_user(age=40 + i, username=f"tutor_rel{i}")
            Guardianship.objects.create(
                athlete=self.menor, guardian=tutor, relation=relacion,
            )
            self.assertIn(
                tutor.pk,
                MinorLodgingPolicy.accredited_adult_ids(
                    self.menor, include_team_staff=False,
                ),
            )

    def test_un_adulto_que_no_es_tutor_de_ninguno_sigue_rechazado(self):
        """Criterio 5: agregar tutores no abre la puerta a terceros."""
        self._segundo_tutor("padre_ajeno_test")
        ajeno = self.make_user(age=38, username="ajeno_multi")
        bed = self.make_bed(Bed.DOUBLE, label="Cama ajena")

        self.assign_room(self.menor)
        with self.assertRaises(ValidationError):
            self.assign_room(ajeno)

        ra_menor = self.menor.event_stays.first().room_assignment
        BedAssignment.objects.create(stay=ra_menor.stay, bed=bed)
        ra_coach = self.assign_room(self.coach)
        with self.assertRaises(ValidationError):
            BedAssignment.objects.create(stay=ra_coach.stay, bed=bed)

    def test_quitar_un_tutor_deja_al_otro_acreditado(self):
        from hospitality.policies import MinorLodgingPolicy

        padre = self._segundo_tutor("padre_baja_hosp")
        Guardianship.objects.filter(
            athlete=self.menor, guardian=self.guardian,
        ).delete()

        permitidos = MinorLodgingPolicy.accredited_adult_ids(
            self.menor, include_team_staff=False,
        )
        self.assertIn(padre.pk, permitidos)
        self.assertNotIn(self.guardian.pk, permitidos)


# =====================================================================
# 3. CIERRE DE HALLAZGOS DE SEGURIDAD
# =====================================================================

class FailClosedAgeTests(LodgingTestBase):
    """Una regla de protección no puede apagarse por un dato faltante."""

    def setUp(self):
        super().setUp()
        self.team, self.coach = self.make_team("Cometas")

    def _atleta_sin_fecha(self, username):
        user = UserFactory(username=username)
        user.birth_date = None
        user.save(update_fields=["birth_date"])
        self.join_team(user, self.team)
        AthleteProfile.objects.create(user=user, emergency_contact="Familia")
        return user

    def test_atleta_sin_fecha_de_nacimiento_cuenta_como_menor(self):
        from hospitality.policies import MinorLodgingPolicy

        self.assertTrue(MinorLodgingPolicy.is_minor(self._atleta_sin_fecha("sin_fecha")))

    def test_atleta_sin_fecha_queda_protegido(self):
        atleta = self._atleta_sin_fecha("sin_fecha2")
        ajeno = self.make_user(age=40, username="ajeno_sf")
        self.assign_room(atleta)
        with self.assertRaises(ValidationError):
            self.assign_room(ajeno)

    def test_no_atleta_sin_fecha_sigue_contando_como_adulto(self):
        """Por ese lado la falta de dato ya era restrictiva: tiene que estar
        acreditado para alojarse con un menor."""
        from hospitality.policies import MinorLodgingPolicy

        adulto = UserFactory(username="adulto_sf")
        adulto.birth_date = None
        adulto.save(update_fields=["birth_date"])
        self.assertFalse(MinorLodgingPolicy.is_minor(adulto))

        menor = self.make_user(age=15, username="menor_sf")
        self.join_team(menor, self.team)
        AthleteProfile.objects.create(user=menor, emergency_contact="F")
        self.assign_room(menor)
        with self.assertRaises(ValidationError):
            self.assign_room(adulto)


class MembershipRoleMappingTests(LodgingTestBase):
    """La acreditación se apoya en los roles que el modelo define de verdad."""

    def setUp(self):
        super().setUp()
        self.team, self.coach = self.make_team("Cometas")
        self.menor = self.make_user(age=15, username="menor_rol")
        self.join_team(self.menor, self.team)
        AthleteProfile.objects.create(user=self.menor, emergency_contact="F")

    def test_headcoach_no_es_un_valor_valido_de_role_in_team(self):
        from teams.models import UserTeamMembership

        validos = {code for code, _ in UserTeamMembership.ROLE_CHOICES}
        self.assertNotIn("HEADCOACH", validos)

    def test_role_in_team_fuera_de_spec_no_acredita(self):
        """Escribir 'HEADCOACH' a mano no debe dar acceso: ese cargo se
        reconoce por Team.coach, no por un literal en la membresía."""
        from hospitality.policies import MinorLodgingPolicy

        impostor = self.make_user(age=40, username="impostor")
        UserTeamMembership.objects.create(
            user=impostor, team=self.team, role_in_team="HEADCOACH",
            status="accepted", is_active=True,
        )
        self.assertNotIn(
            impostor.pk, MinorLodgingPolicy.accredited_adult_ids(self.menor),
        )

    def test_el_head_coach_real_si_acredita(self):
        from hospitality.policies import MinorLodgingPolicy

        self.assertIn(
            self.coach.pk, MinorLodgingPolicy.accredited_adult_ids(self.menor),
        )


class StaleAuthorizationTests(LodgingTestBase):
    """La autorización guardada envejece: hay que poder revalidarla."""

    def setUp(self):
        super().setUp()
        self.team, self.coach = self.make_team("Cometas")
        self.menor = self.make_user(age=15, username="menor_stale")
        self.join_team(self.menor, self.team)
        self.guardian = self.make_user(age=42, username="guardian_stale")
        self.profile = AthleteProfile.objects.create(
            user=self.menor, emergency_contact="F",
        )
        Guardianship.objects.create(athlete=self.menor, guardian=self.guardian)

    def test_quitar_el_tutor_deja_la_asignacion_en_infraccion(self):
        from hospitality.policies import MinorLodgingPolicy

        ra_menor = self.assign_room(self.menor)
        self.assign_room(self.guardian)
        self.assertEqual(MinorLodgingPolicy.audit_stay(ra_menor.stay), [])

        Guardianship.objects.filter(athlete=self.menor).delete()
        self.assertTrue(MinorLodgingPolicy.audit_stay(ra_menor.stay))

    def test_el_check_in_rechaza_un_alojamiento_que_dejo_de_cumplir(self):
        from hospitality.services import HospitalityService

        bed_a = self.make_bed(Bed.SINGLE, label="A")
        bed_b = self.make_bed(Bed.SINGLE, label="B")
        ra_menor = self.assign_room(self.menor)
        ra_guardian = self.assign_room(self.guardian)
        BedAssignment.objects.create(stay=ra_menor.stay, bed=bed_a)
        BedAssignment.objects.create(stay=ra_guardian.stay, bed=bed_b)

        Guardianship.objects.filter(athlete=self.menor).delete()

        with self.assertRaises(ValidationError):
            HospitalityService.check_in(stay=ra_menor.stay, checked_in_by=self.admin)

    def test_audit_event_lista_las_estancias_en_infraccion(self):
        from hospitality.policies import MinorLodgingPolicy

        self.assign_room(self.menor)
        self.assign_room(self.guardian)
        self.assertEqual(MinorLodgingPolicy.audit_event(self.event), {})

        Guardianship.objects.filter(athlete=self.menor).delete()
        self.assertTrue(MinorLodgingPolicy.audit_event(self.event))


class AuditoriaConVariosTutoresTests(LodgingTestBase):
    """Criterio 7: sobre datos con varios tutores, cero falsos positivos."""

    def setUp(self):
        super().setUp()
        self.team, self.coach = self.make_team("Cometas")
        self.menor = self.make_user(age=15, username="menor_audit")
        self.join_team(self.menor, self.team)
        AthleteProfile.objects.create(
            user=self.menor, emergency_contact="Familia",
        )
        self.madre = self.make_user(age=42, username="madre_audit")
        self.padre = self.make_user(age=44, username="padre_audit")
        Guardianship.objects.create(athlete=self.menor, guardian=self.madre)
        Guardianship.objects.create(athlete=self.menor, guardian=self.padre)

    def test_audit_event_no_marca_una_habitacion_con_los_dos_tutores(self):
        from hospitality.policies import MinorLodgingPolicy

        self.assign_room(self.menor)
        self.assign_room(self.madre)
        self.assign_room(self.padre)
        self.assertEqual(MinorLodgingPolicy.audit_event(self.event), {})

    def test_audit_stay_marca_cuando_ya_no_queda_ningun_tutor(self):
        from hospitality.policies import MinorLodgingPolicy

        ra_menor = self.assign_room(self.menor)
        self.assign_room(self.madre)
        self.assertEqual(MinorLodgingPolicy.audit_stay(ra_menor.stay), [])

        Guardianship.objects.filter(athlete=self.menor).delete()
        self.assertTrue(MinorLodgingPolicy.audit_stay(ra_menor.stay))

    def test_guardians_present_at_devuelve_solo_a_quien_viajo(self):
        """La consulta que reemplaza a la designación por viaje."""
        from custody.services.minor_service import MinorAthleteService

        self.assign_room(self.menor)
        self.assign_room(self.madre)

        presentes = MinorAthleteService.guardians_present_at(self.event, self.menor)
        self.assertEqual(list(presentes), [self.madre])

    def test_una_estancia_cancelada_no_cuenta_como_presencia(self):
        from custody.services.minor_service import MinorAthleteService

        ra_madre = self.assign_room(self.madre)
        ra_madre.stay.status = Stay.CANCELLED
        ra_madre.stay.save()

        presentes = MinorAthleteService.guardians_present_at(self.event, self.menor)
        self.assertEqual(list(presentes), [])
