from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0002_alter_productiontask_started_at"),
        ("orders", "0003_alter_orderdesignimage_image"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StageResponsibility",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "stage",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="responsibility",
                        to="production.productionstage",
                    ),
                ),
                (
                    "responsible_role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="primary_stages",
                        to="production.productionrole",
                    ),
                ),
                (
                    "auxiliary_roles",
                    models.ManyToManyField(
                        blank=True,
                        related_name="auxiliary_stages",
                        to="production.productionrole",
                    ),
                ),
            ],
            options={
                "verbose_name": "Responsabilidad de etapa",
                "verbose_name_plural": "Responsabilidades de etapas",
            },
        ),
        migrations.CreateModel(
            name="ErrorReport",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("reported_at", models.DateTimeField(auto_now_add=True)),
                ("area", models.CharField(blank=True, max_length=200)),
                ("error_types", models.JSONField(default=list)),
                ("error_type_other", models.CharField(blank=True, max_length=200)),
                ("description", models.TextField()),
                ("responsible_area", models.CharField(blank=True, max_length=200)),
                ("error_causes", models.JSONField(default=list)),
                ("cause_other", models.CharField(blank=True, max_length=200)),
                ("cause_detail", models.TextField(blank=True)),
                ("error_impacts", models.JSONField(default=list)),
                ("impact_other", models.CharField(blank=True, max_length=200)),
                ("impact_description", models.TextField(blank=True)),
                ("corrective_actions", models.TextField(blank=True)),
                ("prevention_actions", models.TextField(blank=True)),
                (
                    "review_status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pendiente de revisión"),
                            ("REVIEWED", "Revisado"),
                            ("EXCEPTION_GRANTED", "Excepción otorgada"),
                            ("REPOSITION_REQUIRED", "Reposición requerida"),
                        ],
                        default="PENDING",
                        max_length=30,
                    ),
                ),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_notes", models.TextField(blank=True)),
                ("requires_reposition", models.BooleanField(default=False)),
                ("is_exception", models.BooleanField(default=False)),
                ("exception_reason", models.TextField(blank=True)),
                (
                    "reported_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="error_reports_filed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="error_reports",
                        to="orders.order",
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="error_reports",
                        to="production.productionjob",
                    ),
                ),
                (
                    "stage",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="production.productionstage",
                    ),
                ),
                (
                    "responsible",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="error_reports_responsible",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="error_reports_reviewed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Reporte de error",
                "verbose_name_plural": "Reportes de error",
                "ordering": ["-reported_at"],
            },
        ),
    ]
