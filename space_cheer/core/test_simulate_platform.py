"""Asignacion de telefonos en `simulate_platform`.

Regresion: el comando repartia los telefonos con un contador posicional que se
reiniciaba en 5500000000 en cada corrida, mientras que `User.phone` es UNIQUE y
persiste en la base. Al agregarse `tutor2.comets@test.com` (el segundo tutor del
modelo nuevo de custodia), la segunda corrida sobre una base ya sembrada volvio
a caminar numeros ya tomados y reviento con IntegrityError.

Los tests de aca miran el valor que queda en la fila, no que el comando "no
truene": con el contador viejo el fallo era una violacion de unicidad, y basta
con que la base este vacia para que el bug no se note.
"""

import datetime

import pytest

from core.management.commands.simulate_platform import Command
from accounts.models import UserOwnership
from orders.tests.factories import (
    AthleteFactory,
    TeamFactory,
    UserFactory,
    UserTeamMembershipFactory,
)

pytestmark = pytest.mark.django_db

BIRTH = datetime.date(1990, 1, 1)


def _comando():
    """Un Command con los contadores como los deja `handle()`."""
    cmd = Command()
    cmd._emergency_seq = 5500000000
    cmd._curp_seq = 0
    return cmd


def test_no_reasigna_un_telefono_que_ya_tiene_otro_usuario():
    # Cinco usuarios de una corrida anterior ocupan el arranque del contador.
    for i in range(1, 6):
        UserFactory(phone=f"55000000{i:02d}")

    nuevo = UserFactory(phone=None)

    _comando().complete_profile(nuevo, gender="H", birth=BIRTH)

    nuevo.refresh_from_db()
    assert nuevo.phone, "el usuario nuevo quedo sin telefono"
    ocupados = {f"55000000{i:02d}" for i in range(1, 6)}
    assert nuevo.phone not in ocupados


def test_el_telefono_no_depende_del_orden_en_que_el_comando_ve_a_los_usuarios():
    # Cada usuario nuevo que se agregue en medio de `phase_users` corre a los que
    # vienen despues. El telefono tiene que salir del usuario, no de su turno.
    a = UserFactory(phone=None)
    b = UserFactory(phone=None)

    cmd = _comando()
    cmd.complete_profile(a, gender="M", birth=BIRTH)
    cmd.complete_profile(b, gender="H", birth=BIRTH)
    a.refresh_from_db()
    b.refresh_from_db()
    esperado = (a.phone, b.phone)

    a.phone = None
    a.save()
    b.phone = None
    b.save()

    # Segunda corrida, con los mismos usuarios en el orden inverso.
    cmd = _comando()
    cmd.complete_profile(b, gender="H", birth=BIRTH)
    cmd.complete_profile(a, gender="M", birth=BIRTH)
    a.refresh_from_db()
    b.refresh_from_db()

    assert (a.phone, b.phone) == esperado


def test_no_choca_con_los_telefonos_que_dejo_la_numeracion_vieja():
    # El contador viejo repartia telefonos por turno, asi que en cualquier base
    # ya sembrada hay numeros `55...` pegados a pks que no les corresponden.
    nuevo = UserFactory(phone=None)
    UserFactory(phone=f"55{nuevo.pk:08d}")

    _comando().complete_profile(nuevo, gender="H", birth=BIRTH)

    nuevo.refresh_from_db()
    assert nuevo.phone


def test_el_headcoach_queda_como_owner_de_las_atletas_de_su_equipo():
    # `assign_guardian` corta al headcoach que no tiene ownership sobre el
    # atleta, asi que sin estas filas sus pantallas de custodia no se pueden
    # recorrer con el rol que realmente las usa.
    team = TeamFactory()
    a1 = AthleteFactory(phone=None)
    a2 = AthleteFactory(phone=None)
    UserTeamMembershipFactory(user=a1, team=team)
    UserTeamMembershipFactory(user=a2, team=team)

    _comando().grant_team_ownership()

    for atleta in (a1, a2):
        assert UserOwnership.objects.filter(
            owner=team.coach, user=atleta, is_active=True
        ).exists(), f"{atleta.email} sin ownership"


def test_una_corrida_que_revienta_a_la_mitad_no_deja_la_base_a_medias(monkeypatch):
    # Un crash o un kill a mitad de `handle()` dejaba las fases previas
    # grabadas (la primera vez, `tutor2.comets` insertado y sin telefono) y la
    # siguiente corrida arrancaba sobre ese estado roto.
    from django.core.management import call_command

    def fase_1_que_graba(self):
        UserFactory(username="grabado_por_la_fase_1")

    def fase_2_que_revienta(self):
        raise RuntimeError("corte a mitad de la simulacion")

    monkeypatch.setattr(Command, "phase_users", fase_1_que_graba)
    monkeypatch.setattr(Command, "phase_production_config", fase_2_que_revienta)

    with pytest.raises(RuntimeError):
        call_command("simulate_platform")

    from django.contrib.auth import get_user_model
    assert not get_user_model().objects.filter(
        username="grabado_por_la_fase_1"
    ).exists()


def test_sembrar_el_ownership_dos_veces_no_duplica():
    team = TeamFactory()
    atleta = AthleteFactory(phone=None)
    UserTeamMembershipFactory(user=atleta, team=team)

    _comando().grant_team_ownership()
    _comando().grant_team_ownership()

    assert (
        UserOwnership.objects.filter(
            owner=team.coach, user=atleta, is_active=True
        ).count()
        == 1
    )
