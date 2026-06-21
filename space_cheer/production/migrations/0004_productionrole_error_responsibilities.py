from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0003_stageresponsibility_errorreport"),
    ]

    operations = [
        migrations.AddField(
            model_name="productionrole",
            name="error_responsibilities",
            field=models.TextField(
                blank=True,
                help_text="Una responsabilidad por línea. Ej: Tallas incorrectas",
            ),
        ),
    ]
