from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError


# -------------------------------------------------------------
#   ROLES
# -------------------------------------------------------------
class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    requires_curp = models.BooleanField(default=False)
    is_staff_type = models.BooleanField(default=False)
    is_athlete_type = models.BooleanField(default=False)
    is_coach_type = models.BooleanField(default=False)
    allow_dashboard_access = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# -------------------------------------------------------------
#   USER (Custom)
# -------------------------------------------------------------
class User(AbstractUser):

    roles = models.ManyToManyField(Role, related_name="users", blank=True)
    foto_perfil = models.ImageField(
        upload_to="accounts/perfiles/", null=True, blank=True
    )
    curp = models.CharField(max_length=18, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=1,
        choices=[("H", "Hombre"), ("M", "Mujer")],
        null=True,
        blank=True,
    )

    # Consentimientos
    privacy_accepted = models.BooleanField(default=False)
    terms_accepted = models.BooleanField(default=False)
    profile_completed = models.BooleanField(
        default=False
    )  # Marca cuando ya pasó onboarding

    def clean(self):
        # si el usuario aún no existe en DB, no validar roles
        if not self.pk:
            return super().clean()

        if self.roles.filter(requires_curp=True).exists() and not self.curp:
            raise ValidationError(
                {"curp": "Este usuario requiere CURP debido a su rol."}
            )

        if self.curp and len(self.curp) != 18:
            raise ValidationError({"curp": "La CURP debe tener 18 caracteres."})

        super().clean()

    @property
    def is_minor(self):
        if not self.birth_date:
            return False
        today = timezone.now().date()
        age = (
            today.year
            - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )
        return age < 18

    def __str__(self):
        return self.get_full_name() or self.username


# -------------------------------------------------------------
#   USER-DEPEN
# -------------------------------------------------------------
class UserOwnership(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_users",
        help_text="Coach dueño del usuario",
        null=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owner_links",
        help_text="Usuario perteneciente al coach",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("owner", "user")
        indexes = [
            models.Index(fields=["owner", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.owner} → {self.user}"


# -------------------------------------------------------------
#  USER ADDRESS
# -------------------------------------------------------------
class UserAddress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses"
    )
    label = models.CharField(max_length=50, default="Principal")
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=10)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.label} - {self.address}"


# -------------------------------------------------------------
#  ATHLETE PROFILE
# -------------------------------------------------------------
class AthleteProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    emergency_contact = models.CharField(max_length=100)
    emergency_phone = models.CharField(max_length=20, blank=True)

    is_active_competitor = models.BooleanField(default=True)

    # Si es menor, puede requerir un tutor
    guardian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="athletes_under_guardian",
    )

    def __str__(self):
        return f"Perfil atleta: {self.user}"


# -------------------------------------------------------------
#  ATHLETE MEDICAL INFO
# -------------------------------------------------------------
class AthleteMedicalInfo(models.Model):
    athlete = models.OneToOneField(AthleteProfile, on_delete=models.CASCADE)

    allergies = models.TextField(blank=True)
    medications = models.TextField(blank=True)
    medical_notes = models.TextField(blank=True)
    has_insurance = models.BooleanField(default=False)
    insurance_policy_number = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Info médica de {self.athlete.user}"


# -------------------------------------------------------------
#  COACH PROFILE
# -------------------------------------------------------------
class CoachProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    experience_years = models.PositiveIntegerField(default=0)
    certifications = models.TextField(blank=True)

    def __str__(self):
        return f"Coach: {self.user}"


# -------------------------------------------------------------
#  STAFF PROFILE
# -------------------------------------------------------------
class StaffProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    role_description = models.CharField(max_length=255, blank=True)
    staff_id = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Staff: {self.user}"


# -------------------------------------------------------------
#  GUARDIAN / ACOMPANANTE PROFILE
# -------------------------------------------------------------
class GuardianProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    relation = models.CharField(
        max_length=50,
        choices=[
            ("PADRE", "Padre / Madre"),
            ("TUTOR", "Tutor legal"),
            ("ACOMP", "Acompañante"),
        ],
        default="ACOMP",
    )

    def __str__(self):
        return f"Tutor/Acompañante: {self.user}"
