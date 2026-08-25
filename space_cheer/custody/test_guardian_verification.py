"""Respaldo del vínculo del tutor y aviso por carga de atletas.

`relation` se elegía libre en un desplegable, sin documento ni aprobación, y
las tres opciones pesaban igual. La tutela legal es la única que sostiene
decisiones sobre un menor cuando los padres no están: esa sí pide respaldo.

El número de atletas a cargo NO se limita: una tutora que lleva a sus tres
hijas al mismo evento es un caso normal. Se avisa y se sigue.
"""

import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import AthleteProfile, Role
from custody.models import GuardianProfile
from custody.services.minor_service import MinorAthleteService
from orders.tests.factories import UserFactory


class GuardianVerificationTests(TestCase):

    def setUp(self):
        hoy = datetime.date.today()
        self.admin_role, _ = Role.objects.get_or_create(name="ADMIN")
        self.guardian_role, _ = Role.objects.get_or_create(name="GUARDIAN")

        self.admin = UserFactory(username="admin_cust", birth_date=datetime.date(1985, 1, 1))
        self.admin.roles.add(self.admin_role)

        self.tutor = UserFactory(username="tutor_cust", birth_date=datetime.date(1984, 5, 2))
        self.tutor.roles.add(self.guardian_role)
        # Un signal ya crea el GuardianProfile al asignar el rol GUARDIAN.
        self.perfil, _ = GuardianProfile.objects.update_or_create(
            user=self.tutor, defaults={"relation": GuardianProfile.TUTOR},
        )

    def _atleta(self, username):
        menor = UserFactory(
            username=username,
            birth_date=datetime.date.today() - datetime.timedelta(days=365 * 15),
        )
        AthleteProfile.objects.create(
            user=menor, emergency_contact="Familia", guardian=self.tutor,
        )
        return menor

    # ── respaldo del vínculo ─────────────────────────────────────────
    def test_la_tutela_legal_nace_sin_verificar(self):
        self.assertTrue(self.perfil.requires_proof)
        self.assertFalse(self.perfil.is_verified)
        self.assertTrue(self.perfil.proof_pending)

    def test_padre_y_acompanante_no_piden_respaldo(self):
        for relacion in (GuardianProfile.PADRE, GuardianProfile.ACOMP):
            perfil = GuardianProfile(relation=relacion)
            self.assertFalse(perfil.requires_proof)
            self.assertFalse(perfil.proof_pending)

    def test_verificar_deja_constancia_de_quien_y_cuando(self):
        perfil = MinorAthleteService.verify_guardianship(
            guardian=self.tutor, verified_by=self.admin,
            legal_document="Acta 1234/2026",
        )
        self.assertTrue(perfil.is_verified)
        self.assertFalse(perfil.proof_pending)
        self.assertEqual(perfil.verified_by, self.admin)
        self.assertEqual(perfil.legal_document, "Acta 1234/2026")
        self.assertIsNotNone(perfil.verified_at)

    def test_solo_un_administrador_verifica(self):
        cualquiera = UserFactory(username="cualquiera", birth_date=datetime.date(1990, 1, 1))
        with self.assertRaises(PermissionDenied):
            MinorAthleteService.verify_guardianship(
                guardian=self.tutor, verified_by=cualquiera,
            )

    def test_no_se_verifica_lo_que_no_pide_respaldo(self):
        self.perfil.relation = GuardianProfile.PADRE
        self.perfil.save(update_fields=["relation"])
        with self.assertRaises(ValidationError):
            MinorAthleteService.verify_guardianship(
                guardian=self.tutor, verified_by=self.admin,
            )

    def test_cambiar_la_relacion_invalida_la_verificacion(self):
        """Se revisó un vínculo distinto del que ahora se afirma."""
        menor = self._atleta("menor_rel")
        MinorAthleteService.verify_guardianship(
            guardian=self.tutor, verified_by=self.admin, legal_document="Acta 1",
        )

        MinorAthleteService.update_guardian_relation(
            athlete=menor, relation=GuardianProfile.PADRE, updated_by=self.admin,
        )
        self.perfil.refresh_from_db()
        self.assertFalse(self.perfil.is_verified)
        self.assertEqual(self.perfil.legal_document, "")

    # ── carga de atletas: se avisa, no se bloquea ────────────────────
    def test_no_hay_tope_de_atletas_por_tutor(self):
        for i in range(GuardianProfile.SOFT_ATHLETE_LIMIT + 2):
            self._atleta(f"menor_carga{i}")
        self.perfil.refresh_from_db()
        self.assertEqual(
            self.perfil.athlete_count, GuardianProfile.SOFT_ATHLETE_LIMIT + 2,
        )

    def test_pasar_el_umbral_solo_lo_marca(self):
        for i in range(GuardianProfile.SOFT_ATHLETE_LIMIT):
            self._atleta(f"menor_umbral{i}")
        self.assertFalse(self.perfil.over_soft_limit)

        self._atleta("menor_uno_mas")
        self.assertTrue(self.perfil.over_soft_limit)

    def test_guardians_needing_attention_explica_el_motivo(self):
        pendientes = MinorAthleteService.guardians_needing_attention([self.tutor])
        self.assertEqual(len(pendientes), 1)
        perfil, motivos = pendientes[0]
        self.assertEqual(perfil, self.perfil)
        self.assertIn("declara tutela legal sin verificar", motivos)

    def test_un_tutor_en_regla_no_aparece_en_la_lista(self):
        MinorAthleteService.verify_guardianship(
            guardian=self.tutor, verified_by=self.admin, legal_document="Acta 2",
        )
        self.assertEqual(
            MinorAthleteService.guardians_needing_attention([self.tutor]), [],
        )
