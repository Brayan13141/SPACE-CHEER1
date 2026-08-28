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

from accounts.models import AthleteProfile, Role
from custody.models import Guardianship
from custody.services.minor_service import MinorAthleteService
from orders.tests.factories import UserFactory


class GuardianVerificationTests(TestCase):

    def setUp(self):
        self.admin_role, _ = Role.objects.get_or_create(name="ADMIN")
        self.guardian_role, _ = Role.objects.get_or_create(name="GUARDIAN")

        self.admin = UserFactory(
            username="admin_cust", birth_date=datetime.date(1985, 1, 1),
        )
        self.admin.roles.add(self.admin_role)

        self.tutor = UserFactory(
            username="tutor_cust", birth_date=datetime.date(1984, 5, 2),
        )
        self.tutor.roles.add(self.guardian_role)

        self.menor = self._atleta("menor_cust")
        self.vinculo = Guardianship.objects.create(
            athlete=self.menor, guardian=self.tutor, relation=Guardianship.TUTOR,
        )

    def _atleta(self, username):
        menor = UserFactory(
            username=username,
            birth_date=datetime.date.today() - datetime.timedelta(days=365 * 15),
        )
        # update_or_create y no create: si alguien le agrega el rol ATHLETE a
        # este helper, el signal de accounts ya habrá creado el perfil.
        AthleteProfile.objects.update_or_create(
            user=menor, defaults={"emergency_contact": "Familia"},
        )
        return menor

    def _vinculo_extra(self, username, relation=Guardianship.ACOMP):
        return Guardianship.objects.create(
            athlete=self._atleta(username), guardian=self.tutor, relation=relation,
        )

    # ── respaldo del vínculo ─────────────────────────────────────────
    def test_la_tutela_legal_nace_sin_verificar(self):
        self.assertTrue(self.vinculo.requires_proof)
        self.assertFalse(self.vinculo.is_verified)
        self.assertTrue(self.vinculo.proof_pending)

    def test_padre_y_acompanante_no_piden_respaldo(self):
        for relacion in (Guardianship.PADRE, Guardianship.ACOMP):
            vinculo = Guardianship(relation=relacion)
            self.assertFalse(vinculo.requires_proof)
            self.assertFalse(vinculo.proof_pending)

    def test_verificar_deja_constancia_de_quien_y_cuando(self):
        vinculo = MinorAthleteService.verify_guardianship(
            guardianship=self.vinculo, verified_by=self.admin,
            legal_document="Acta 1234/2026",
        )
        self.assertTrue(vinculo.is_verified)
        self.assertFalse(vinculo.proof_pending)
        self.assertEqual(vinculo.verified_by, self.admin)
        self.assertEqual(vinculo.legal_document, "Acta 1234/2026")
        self.assertIsNotNone(vinculo.verified_at)

    def test_solo_un_administrador_verifica(self):
        cualquiera = UserFactory(
            username="cualquiera", birth_date=datetime.date(1990, 1, 1),
        )
        with self.assertRaises(PermissionDenied):
            MinorAthleteService.verify_guardianship(
                guardianship=self.vinculo, verified_by=cualquiera,
            )

    def test_no_se_verifica_lo_que_no_pide_respaldo(self):
        self.vinculo.relation = Guardianship.PADRE
        self.vinculo.save(update_fields=["relation"])
        with self.assertRaises(ValidationError):
            MinorAthleteService.verify_guardianship(
                guardianship=self.vinculo, verified_by=self.admin,
            )

    def test_cambiar_la_relacion_invalida_la_verificacion(self):
        """Se revisó un vínculo distinto del que ahora se afirma."""
        MinorAthleteService.verify_guardianship(
            guardianship=self.vinculo, verified_by=self.admin,
            legal_document="Acta 1",
        )

        MinorAthleteService.update_guardian_relation(
            athlete=self.menor, guardian=self.tutor,
            relation=Guardianship.PADRE, updated_by=self.admin,
        )
        self.vinculo.refresh_from_db()
        self.assertFalse(self.vinculo.is_verified)
        self.assertEqual(self.vinculo.legal_document, "")

    # ── carga de atletas: se avisa, no se bloquea ────────────────────
    def test_no_hay_tope_de_atletas_por_tutor(self):
        for i in range(Guardianship.SOFT_ATHLETE_LIMIT + 1):
            self._vinculo_extra(f"menor_carga{i}")
        # + el vínculo del setUp
        self.assertEqual(
            Guardianship.athlete_count_for(self.tutor),
            Guardianship.SOFT_ATHLETE_LIMIT + 2,
        )

    def test_pasar_el_umbral_solo_lo_marca(self):
        # el setUp ya dejó 1 vínculo: faltan LIMIT-1 para llegar al umbral
        for i in range(Guardianship.SOFT_ATHLETE_LIMIT - 1):
            ultimo = self._vinculo_extra(f"menor_umbral{i}")
        self.assertFalse(ultimo.over_soft_limit)

        uno_mas = self._vinculo_extra("menor_uno_mas")
        self.assertTrue(uno_mas.over_soft_limit)

    def test_guardians_needing_attention_explica_el_motivo(self):
        pendientes = MinorAthleteService.guardians_needing_attention([self.tutor])
        self.assertEqual(len(pendientes), 1)
        vinculo, motivos = pendientes[0]
        self.assertEqual(vinculo, self.vinculo)
        self.assertIn("declara tutela legal sin verificar", motivos)

    def test_un_vinculo_en_regla_no_aparece_en_la_lista(self):
        MinorAthleteService.verify_guardianship(
            guardianship=self.vinculo, verified_by=self.admin,
            legal_document="Acta 2",
        )
        self.assertEqual(
            MinorAthleteService.guardians_needing_attention([self.tutor]), [],
        )
