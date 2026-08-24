from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


# ── Catalog ──────────────────────────────────────────────────────────────────

class RoomFeature(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True)  # e.g. "bi-wifi"

    class Meta:
        verbose_name = "Característica de habitación"
        verbose_name_plural = "Características de habitaciones"

    def __str__(self):
        return self.name


# ── Hotel ─────────────────────────────────────────────────────────────────────

class Hotel(models.Model):
    event = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='hotels',
    )
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    website = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='hospitality/hotels/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'name')
        verbose_name = "Hotel"
        verbose_name_plural = "Hoteles"

    def __str__(self):
        return f"{self.name} ({self.event})"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ── RoomType ──────────────────────────────────────────────────────────────────

class RoomType(models.Model):
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='room_types',
    )
    name = models.CharField(max_length=100)  # "Habitación Doble", "Suite Junior"
    capacity = models.PositiveIntegerField()  # max people
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    features = models.ManyToManyField(
        RoomFeature,
        blank=True,
        related_name='room_types',
    )

    class Meta:
        unique_together = ('hotel', 'name')
        verbose_name = "Tipo de habitación"
        verbose_name_plural = "Tipos de habitaciones"

    def __str__(self):
        return f"{self.name} — {self.hotel}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ── Room ──────────────────────────────────────────────────────────────────────

class Room(models.Model):
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='rooms',
    )
    room_type = models.ForeignKey(
        RoomType,
        on_delete=models.PROTECT,
        related_name='rooms',
    )
    room_number = models.CharField(max_length=20)
    floor = models.PositiveIntegerField(default=1)
    notes = models.TextField(blank=True)
    is_available = models.BooleanField(default=True)

    class Meta:
        unique_together = ('hotel', 'room_number', 'floor')
        verbose_name = "Habitación"
        verbose_name_plural = "Habitaciones"

    def __str__(self):
        return f"#{self.room_number} — {self.hotel}"

    def _validate_room_type_hotel(self):
        if self.room_type_id and self.hotel_id:
            if self.room_type.hotel_id != self.hotel_id:
                raise ValidationError({'room_type': "El tipo de habitación no pertenece a este hotel."})

    def _validate_unique_room(self):
        if self.hotel_id and self.room_number and self.floor is not None:
            qs = Room.objects.filter(
                hotel_id=self.hotel_id,
                room_number=self.room_number,
                floor=self.floor,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'room_number': (
                        f"Ya existe una habitación con el número '{self.room_number}' "
                        f"en el piso {self.floor} de este hotel."
                    )
                })

    def clean(self):
        self._validate_room_type_hotel()
        self._validate_unique_room()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ── Bed ───────────────────────────────────────────────────────────────────────

class Bed(models.Model):
    SINGLE = 'SINGLE'
    DOUBLE = 'DOUBLE'
    QUEEN = 'QUEEN'
    KING = 'KING'
    BUNK = 'BUNK'

    BED_TYPE_CHOICES = [
        (SINGLE, 'Individual'),
        (DOUBLE, 'Doble'),
        (QUEEN, 'Queen'),
        (KING, 'King'),
        (BUNK, 'Litera'),
    ]

    # Cuántas personas duerme cada tipo de cama cuando la cama no lo declara.
    DEFAULT_CAPACITY = {
        SINGLE: 1,
        DOUBLE: 2,
        QUEEN: 2,
        KING: 2,
        BUNK: 2,
    }

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='beds',
    )
    bed_type = models.CharField(max_length=20, choices=BED_TYPE_CHOICES, default=SINGLE)
    label = models.CharField(max_length=50, blank=True)  # "Cama A", "Cama derecha"
    capacity = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Capacidad",
        help_text=(
            "Cuántas personas duermen en esta cama. Vacío = el default de su "
            "tipo (individual 1, el resto 2). Úsalo para una matrimonial "
            "angosta o una litera de tres."
        ),
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Cama"
        verbose_name_plural = "Camas"

    def __str__(self):
        return f"{self.get_bed_type_display()} — Hab. {self.room}"

    @property
    def effective_capacity(self):
        """Capacidad declarada, o la del tipo de cama si no se declaró."""
        if self.capacity:
            return self.capacity
        return self.DEFAULT_CAPACITY.get(self.bed_type, 1)

    @property
    def current_occupancy(self):
        """Huéspedes con estancia viva en esta cama."""
        if not self.pk:
            return 0
        return self.assignments.exclude(stay__status=Stay.CANCELLED).count()

    def _validate_capacity(self):
        if self.capacity is not None and self.capacity < 1:
            raise ValidationError({'capacity': "La capacidad debe ser al menos 1."})
        # No dejar la cama sobrevendida al reducir su capacidad.
        if self.pk and self.capacity is not None:
            ocupada = self.current_occupancy
            if self.capacity < ocupada:
                raise ValidationError({
                    'capacity': (
                        f"No puedes dejar la capacidad en {self.capacity}: la cama "
                        f"ya tiene {ocupada} huésped(es) asignado(s)."
                    )
                })

    def clean(self):
        self._validate_capacity()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ── HospitalityPreference ─────────────────────────────────────────────────────

class HospitalityPreference(models.Model):
    event = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    event_participant = models.ForeignKey(
        'events.EventParticipant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    preferred_hotel = models.ForeignKey(
        Hotel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    preferred_room_type = models.ForeignKey(
        RoomType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    preferred_features = models.ManyToManyField(
        RoomFeature,
        blank=True,
        related_name='preferences',
    )
    roommate_preferences = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='roommate_requested_by',
    )
    special_needs = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('event', 'user')
        verbose_name = "Preferencia de hospitalidad"
        verbose_name_plural = "Preferencias de hospitalidad"

    def __str__(self):
        return f"Preferencia de {self.user} — {self.event}"

    def _validate_hotel_event(self):
        if self.preferred_hotel_id and self.event_id:
            if self.preferred_hotel.event_id != self.event_id:
                raise ValidationError({'preferred_hotel': "El hotel no pertenece a este evento."})

    def _validate_room_type_hotel(self):
        if self.preferred_room_type_id and self.preferred_hotel_id:
            if self.preferred_room_type.hotel_id != self.preferred_hotel_id:
                raise ValidationError({'preferred_room_type': "El tipo de habitación no pertenece al hotel preferido."})

    def clean(self):
        self._validate_hotel_event()
        self._validate_room_type_hotel()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ── Stay ──────────────────────────────────────────────────────────────────────

class Stay(models.Model):
    REQUESTED = 'REQUESTED'
    CONFIRMED = 'CONFIRMED'
    CHECKED_IN = 'CHECKED_IN'
    CHECKED_OUT = 'CHECKED_OUT'
    CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (REQUESTED, 'Solicitado'),
        (CONFIRMED, 'Confirmado'),
        (CHECKED_IN, 'Check-in realizado'),
        (CHECKED_OUT, 'Check-out realizado'),
        (CANCELLED, 'Cancelado'),
    ]

    event = models.ForeignKey(
        'events.Event',
        on_delete=models.PROTECT,
        related_name='stays',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='event_stays',
    )
    event_participant = models.ForeignKey(
        'events.EventParticipant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stay',
    )
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    check_in_date = models.DateField(null=True, blank=True)
    check_out_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=REQUESTED)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stays_created_by_me',
    )

    class Meta:
        unique_together = ('event', 'user')
        verbose_name = "Estancia"
        verbose_name_plural = "Estancias"

    def __str__(self):
        return f"Estancia de {self.user} — {self.event}"

    @property
    def nights(self):
        # returns number of nights if both dates are set
        if self.check_in_date and self.check_out_date:
            return (self.check_out_date - self.check_in_date).days
        return None

    def _validate_dates(self):
        if self.check_in_date and self.check_out_date:
            if self.check_out_date <= self.check_in_date:
                raise ValidationError({
                    'check_out_date': "La fecha de check-out debe ser posterior a la de check-in.",
                })

    def _validate_hotel_event(self):
        if self.hotel_id and self.event_id:
            if self.hotel.event_id != self.event_id:
                raise ValidationError({'hotel': "El hotel no pertenece a este evento."})

    def clean(self):
        self._validate_dates()
        self._validate_hotel_event()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ── RoomAssignment ────────────────────────────────────────────────────────────

class RoomAssignment(models.Model):
    stay = models.OneToOneField(
        Stay,
        on_delete=models.CASCADE,
        related_name='room_assignment',
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name='assignments',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='room_assignments_made',
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Asignación de habitación"
        verbose_name_plural = "Asignaciones de habitaciones"

    def __str__(self):
        return f"Hab. {self.room} → {self.stay}"

    def _validate_hotel_consistency(self):
        if self.stay_id and self.room_id:
            stay = self.stay
            if stay.hotel_id and self.room.hotel_id != stay.hotel_id:
                raise ValidationError({'room': "La habitación no pertenece al hotel de la estancia."})

    def _validate_room_capacity(self):
        if not self.room_id:
            return
        exclude_pk = self.pk if self.pk else 0
        current_count = RoomAssignment.objects.filter(
            room=self.room
        ).exclude(
            stay__status=Stay.CANCELLED
        ).exclude(
            pk=exclude_pk
        ).count()
        if current_count >= self.room.room_type.capacity:
            raise ValidationError({'room': "La habitación ha alcanzado su capacidad máxima."})

    def _validate_minor_lodging(self):
        """Un menor no comparte habitación con adultos que no sean su tutor
        o el cuerpo técnico de su equipo (LGDNNA)."""
        from hospitality.policies import MinorLodgingPolicy

        if not self.room_id or not self.stay_id:
            return
        if self.stay.status == Stay.CANCELLED:
            return
        MinorLodgingPolicy.validate_room(
            self.room,
            incoming_user=self.stay.user,
            exclude_stay_id=self.stay_id,
        )

    def clean(self):
        self._validate_hotel_consistency()
        self._validate_room_capacity()
        self._validate_minor_lodging()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ── BedAssignment ─────────────────────────────────────────────────────────────

class BedAssignment(models.Model):
    stay = models.ForeignKey(
        Stay,
        on_delete=models.CASCADE,
        related_name='bed_assignments',
    )
    bed = models.ForeignKey(
        Bed,
        on_delete=models.PROTECT,
        related_name='assignments',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bed_assignments_made',
    )
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('stay', 'bed')
        verbose_name = "Asignación de cama"
        verbose_name_plural = "Asignaciones de camas"

    def __str__(self):
        return f"Cama {self.bed} → {self.stay}"

    def _validate_bed_capacity(self):
        """La cama admite tantos huéspedes como su capacidad efectiva: el
        default de su tipo, o el valor declarado en la cama."""
        if not self.bed_id:
            return
        exclude_pk = self.pk if self.pk else 0
        ocupantes = BedAssignment.objects.filter(
            bed=self.bed
        ).exclude(
            stay__status=Stay.CANCELLED
        ).exclude(
            pk=exclude_pk
        ).count()
        capacidad = self.bed.effective_capacity
        if ocupantes >= capacidad:
            if capacidad == 1:
                mensaje = "Esta cama ya está asignada a otro huésped."
            else:
                mensaje = (
                    f"Esta cama ya alcanzó su capacidad ({capacidad} personas)."
                )
            raise ValidationError({'bed': mensaje})

    def _validate_minor_lodging(self):
        """Compartir cama es más estricto que compartir cuarto, pero la regla
        es la misma: con un menor solo duerme su tutor o cuerpo técnico."""
        from hospitality.policies import MinorLodgingPolicy

        if not self.bed_id or not self.stay_id:
            return
        if self.stay.status == Stay.CANCELLED:
            return
        MinorLodgingPolicy.validate_bed(
            self.bed,
            incoming_user=self.stay.user,
            exclude_stay_id=self.stay_id,
        )

    def _validate_room_consistency(self):
        if not self.stay_id or not self.bed_id:
            return
        try:
            room_assignment = self.stay.room_assignment
        except Stay.room_assignment.RelatedObjectDoesNotExist:
            return
        if self.bed.room_id != room_assignment.room_id:
            raise ValidationError({'bed': "La cama no pertenece a la habitación asignada a esta estancia."})

    def clean(self):
        self._validate_bed_capacity()
        self._validate_room_consistency()
        self._validate_minor_lodging()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
