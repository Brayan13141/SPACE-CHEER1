from django.db import models
from django.conf import settings
from django.utils import timezone
import secrets


# -------------------------
# Categoria / Nivel
# -------------------------
class TeamCategory(models.Model):
    name = models.CharField(max_length=100)
    level = models.PositiveIntegerField(
        default=0, help_text="Nivel jerárquico (0 = base, mayor = más alto)"
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["level", "name"]
        unique_together = ("name", "level")

    def __str__(self):
        return f"{self.name} (Nivel {self.level})" if self.level else self.name


GLOBAL_ROLE_HIERARCHY = {
    "ADMIN": ["ADMIN", "HEADCOACH", "COACH", "STAFF", "ATLETA", "ACOMPANANTE"],
    "HEADCOACH": ["HEADCOACH", "COACH", "STAFF", "ATLETA", "ACOMPANANTE"],
    "COACH": ["COACH", "STAFF", "ATLETA", "ACOMPANANTE"],
    "STAFF": ["STAFF", "ACOMPANANTE"],
    "ATLETA": ["ATLETA", "ACOMPANANTE"],
    "ACOMPANANTE": ["ACOMPANANTE"],
}


# -------------------------
# Team
# -------------------------
class Team(models.Model):
    name = models.CharField(max_length=100, blank=False, null=False)
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coached_teams",
        help_text="Entrenador principal del equipo",
    )
    address = models.CharField(max_length=255, blank=True, null=False)
    city = models.CharField(max_length=100, blank=False, null=False)
    phone = models.CharField(max_length=20, blank=False, null=False)
    logo = models.ImageField(upload_to="team_logos/", blank=True, null=True)
    category = models.ForeignKey(
        TeamCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    join_code = models.CharField(max_length=12, unique=True, editable=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at", "name"]

    def save(self, *args, **kwargs):
        if not self.join_code:
            # generar código seguro y legible
            # intentamos hasta generar un código único
            for _ in range(10):
                code = secrets.token_hex(3).upper()  # 6 hex chars
                if not Team.objects.filter(join_code=code).exists():
                    self.join_code = code
                    break
                else:
                    raise RuntimeError(
                        "No se pudo generar un join_code único. Contacta al administrador."
                    )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} — {self.coach.get_full_name() or self.coach.username}"


# -------------------------
# Membership con estado
# -------------------------
class UserTeamMembership(models.Model):
    ROLE_CHOICES = [
        ("ATLETA", "Atleta"),
        ("COACH", "Coach"),
        ("STAFF", "Staff"),
    ]

    ROLE_COMPATIBILITY = {
        "ATLETA": "is_athlete_type",
        "HEADCOACH": "is_coach_type",
        "COACH": "is_coach_type",
        "STAFF": "is_staff_type",
        "ACOMPAÑANTE": "is_athlete_type",
    }

    STATUS_CHOICES = [
        ("pending", "Pendiente"),
        ("accepted", "Aceptado"),
        ("rejected", "Rechazado"),
        ("inactive", "Inactivo"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")

    role_in_team = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default="member"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    date_joined = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "team")
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.user.username} → {self.team.name} ({self.status})"

    def accept(self):
        self.status = "accepted"
        self.is_active = True
        self.save()

    def reject(self):
        self.status = "rejected"
        self.is_active = False
        self.save()

    def activate(self, role=None):
        if role:
            self.role_in_team = role
        self.status = "accepted"
        self.is_active = True
        self.end_date = None
        self.save()

    def deactivate(self):
        self.status = "inactive"
        self.is_active = False
        self.end_date = timezone.now().date()
        self.save()


class TeamSong(models.Model):
    """
    Canciones de un equipo. Puede opcionalmente pertenecer a una categoría específica
    (ej: una versión para la categoría Novatos 1, otra para Elite).
    """

    team = models.ForeignKey(
        "teams.Team", on_delete=models.CASCADE, related_name="songs"
    )
    category = models.ForeignKey(
        "teams.TeamCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="songs",
    )
    name = models.CharField(max_length=200, help_text="Nombre de la canción / pista")
    audio = models.FileField(upload_to="teams/songs/")
    order = models.PositiveIntegerField(
        default=0, help_text="Orden dentro de la lista (0 = primero)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]
        unique_together = (
            "team",
            "category",
            "order",
        )  # evita dos canciones con el mismo order en la misma team+category

    def __str__(self):
        cat = f" - {self.category}" if self.category else ""
        return f"{self.team.name}{cat}: {self.name}"
