from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_notificationpreferences_privacysettings_piiaccesslog'),
    ]

    operations = [
        migrations.DeleteModel(
            name='GuardianProfile',
        ),
    ]
