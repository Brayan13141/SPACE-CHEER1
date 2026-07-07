from django.db import models


class LandingSettings(models.Model):
    """
    Configuración singleton para la landing page.
    Solo puede existir una instancia (pk=1).
    """

    # Hero section
    hero_badge = models.CharField(
        max_length=100,
        default='SPACE CHEER',
        verbose_name='Badge del héroe'
    )
    hero_title = models.CharField(
        max_length=200,
        default='Eleva tu espíritu con SPACE CHEER',
        verbose_name='Título del héroe'
    )
    hero_paragraph = models.TextField(
        default='La plataforma líder para competencias, entrenamientos y comunidad de cheerleading. Únete a miles de atletas y entrenadores que confían en nosotros.',
        verbose_name='Párrafo del héroe'
    )
    hero_image = models.ImageField(
        upload_to='core/landing/',
        null=True,
        blank=True,
        verbose_name='Imagen del héroe'
    )

    # Stats section (3 estadísticas)
    stat1_number = models.CharField(
        max_length=50,
        default='500+',
        verbose_name='Estadística 1 - Número'
    )
    stat1_label = models.CharField(
        max_length=50,
        default='Equipos registrados',
        verbose_name='Estadística 1 - Etiqueta'
    )
    stat2_number = models.CharField(
        max_length=50,
        default='50+',
        verbose_name='Estadística 2 - Número'
    )
    stat2_label = models.CharField(
        max_length=50,
        default='Eventos al año',
        verbose_name='Estadística 2 - Etiqueta'
    )
    stat3_number = models.CharField(
        max_length=50,
        default='10K+',
        verbose_name='Estadística 3 - Número'
    )
    stat3_label = models.CharField(
        max_length=50,
        default='Atletas activos',
        verbose_name='Estadística 3 - Etiqueta'
    )

    # CTA section
    cta_title = models.CharField(
        max_length=200,
        default='¿Listo para competir?',
        verbose_name='Título CTA'
    )
    cta_paragraph = models.TextField(
        default='Regístrate hoy y lleva a tu equipo al siguiente nivel. Inscripciones abiertas para la próxima temporada.',
        verbose_name='Párrafo CTA'
    )

    class Meta:
        verbose_name = 'Configuración de Landing'
        verbose_name_plural = 'Configuración de Landing'

    def __str__(self):
        return 'Configuración de Landing Page'

    @classmethod
    def get_solo(cls):
        """
        Retorna la única instancia de LandingSettings.
        La crea si no existe (pk=1).
        """
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        # Forzar pk=1 para mantener el patrón singleton
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Evitar eliminación del singleton
        pass