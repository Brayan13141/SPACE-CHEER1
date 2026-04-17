from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GuardianProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('relation', models.CharField(
                    choices=[
                        ('PADRE', 'Padre / Madre'),
                        ('TUTOR', 'Tutor legal'),
                        ('ACOMP', 'Acompañante'),
                    ],
                    default='ACOMP',
                    max_length=50,
                )),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='guardianprofile',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Perfil de Guardian',
                'verbose_name_plural': 'Perfiles de Guardian',
            },
        ),
    ]
