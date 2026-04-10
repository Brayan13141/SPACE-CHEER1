from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


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
    curp_validator = RegexValidator(
        regex=r"^[A-Z]{4}\d{6}[HM](AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)[B-DF-HJ-NP-TV-Z]{3}[A-Z0-9]\d$",
        message="El formato de CURP no es válido.",
        code="curp_invalida",
    )

    curp = models.CharField(
        max_length=18,
        unique=True,
        null=True,
        blank=True,
        validators=[curp_validator],
    )

    email = models.EmailField(
        verbose_name="email address",
        max_length=254,
        unique=True,  # Email único a nivel de base de datos
        error_messages={"unique": "Ya existe un usuario con este correo electrónico."},
    )

    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,  #  Permite NULL para múltiples usuarios sin teléfono
        unique=True,  #  Si tiene valor, debe ser único
        error_messages={"unique": "Ya existe un usuario con este número de teléfono."},
    )

    # ═══════════════════════════════════════════════════════════

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
        """
        Validación personalizada a nivel de modelo
        """

        #  NO validar en superuser
        if self.is_superuser:
            return super().clean()

        if not self.profile_completed:
            return super().clean()

        if self.email:
            # Normalizar email (lowercase y trim)
            self.email = self.email.lower().strip()

        if self.birth_date:
            if self.birth_date > timezone.now().date():
                raise ValidationError(
                    {
                        "birth_date": "La fecha de nacimiento no puede estar en el futuro."
                    }
                )

        if self.phone:
            # Normalizar teléfono (eliminar espacios, guiones y paréntesis)
            self.phone = (
                self.phone.strip()
                .replace(" ", "")
                .replace("-", "")
                .replace("(", "")
                .replace(")", "")
            )

            # Validar que solo contenga dígitos
            if not self.phone.isdigit():
                raise ValidationError(
                    {"phone": "El teléfono solo debe contener números."}
                )

            # Validar longitud (10 dígitos para México)
            if len(self.phone) != 10:
                raise ValidationError(
                    {"phone": "El teléfono debe tener exactamente 10 dígitos."}
                )

            # Verificar duplicados excluyendo la instancia actual
            if User.objects.filter(phone=self.phone).exclude(pk=self.pk).exists():
                raise ValidationError(
                    {"phone": "Ya existe un usuario con este número de teléfono."}
                )

        # Evitar validaciones si roles aún no están listos
        if not self.pk:
            return super().clean()

        if self.roles.filter(requires_curp=True).exists() and not self.curp:
            raise ValidationError({"curp": "Este usuario requiere CURP."})

        if self.curp:
            curp = self.curp.upper().strip()

            if len(curp) != 18:
                raise ValidationError({"curp": "La CURP debe tener 18 caracteres."})

            self.curp = curp  # Normalizar a mayúsculas

        super().clean()

    @property
    def is_headcoach(self):
        return self.roles.filter(name="HEADCOACH").exists()

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
    deactivated_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        # unique_together solo aplica a registros ACTIVOS
        # No ponemos unique en el modelo, lo manejamos con constraint condicional
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "user"],
                condition=models.Q(is_active=True),
                name="unique_active_ownership",
            )
        ]
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
    label = models.CharField(
        max_length=50, help_text="Etiqueta para identificar la dirección"
    )
    address = models.CharField(max_length=255, help_text="Calle y número")
    city = models.CharField(max_length=100, help_text="Ciudad")
    zip_code = models.CharField(max_length=10, help_text="Código postal")
    is_default = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_default:
            UserAddress.objects.filter(user=self.user, is_default=True).exclude(
                pk=self.pk
            ).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.label} - {self.address}"


# -------------------------------------------------------------
#  ATHLETE PROFILE
# -------------------------------------------------------------
class AthleteProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    emergency_contact = models.CharField(
        max_length=100, help_text="Contacto de emergencia"
    )
    emergency_phone = models.CharField(
        max_length=20, blank=True, help_text="Teléfono de emergencia"
    )

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
