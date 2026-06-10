import logging
import secrets
from django.db import transaction
from django.db.models import ProtectedError

from teams.models import Team, UserTeamMembership

logger = logging.getLogger(__name__)


class TeamService:

    @staticmethod
    @transaction.atomic
    def create_team(*, form) -> Team:
        """
        Guarda el equipo y automáticamente registra al coach como HEADCOACH activo.
        La transacción garantiza que si falla la membresía, no queda el equipo huérfano.
        """
        team = form.save()

        UserTeamMembership.objects.create(
            user=team.coach,
            team=team,
            role_in_team="HEADCOACH",
            status="accepted",
            is_active=True,
        )

        logger.info("Equipo creado: %s (coach=%s)", team.name, team.coach)
        return team

    @staticmethod
    def regenerate_join_code(team: Team) -> Team:
        """Genera un nuevo join_code único e invalida el anterior."""
        for _ in range(10):
            code = secrets.token_hex(3).upper()
            if not Team.objects.filter(join_code=code).exists():
                team.join_code = code
                team.save(update_fields=["join_code"])
                logger.info("join_code regenerado para equipo %s", team.id)
                return team
        raise RuntimeError("No se pudo generar un join_code único.")

    @staticmethod
    def delete_team(*, team: Team) -> tuple[bool, str]:
        """
        Intenta eliminar un equipo.
        Retorna (True, mensaje_éxito) o (False, mensaje_error) sin lanzar excepción.
        La vista no debería contener esta lógica de dominio.
        """
        nombre = team.name
        try:
            team.delete()
            logger.info("Equipo eliminado: %s", nombre)
            return True, f"Equipo '{nombre}' eliminado exitosamente."
        except ProtectedError as e:
            orders = [o for o in e.protected_objects if o.__class__.__name__ == "Order"]
            products = [
                p for p in e.protected_objects if p.__class__.__name__ == "Product"
            ]
            partes = []
            if orders:
                partes.append(f"{len(orders)} orden(es)")
            if products:
                partes.append(f"{len(products)} producto(s) exclusivo(s)")
            msg = (
                f"No se puede eliminar '{nombre}' porque tiene "
                f"{' y '.join(partes)} asociados. "
                "Cancela o reasigna esos registros antes de eliminarlo."
            )
            logger.warning("Intento de borrar equipo protegido: %s — %s", nombre, msg)
            return False, msg
