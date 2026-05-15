"""
Migración de schema: cifra CURP y dirección.

Cambios:
  - accounts_user.curp: VARCHAR(18) UNIQUE → TEXT (sin unique)
  - accounts_user.curp_hash: nueva columna CHAR(64) UNIQUE
  - accounts_useraddress.address: VARCHAR(255) → TEXT
  - accounts_useraddress.city: VARCHAR(100) → TEXT
  - accounts_useraddress.zip_code: VARCHAR(10) → TEXT

Después de esta migración los valores existentes quedan en texto plano.
La migración 0008 los cifra.
"""

import django.core.validators
from django.db import migrations, models

import accounts.fields


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_coachprofile_approval_status'),
    ]

    operations = [
        # 1. Agregar curp_hash antes de tocar curp
        migrations.AddField(
            model_name='user',
            name='curp_hash',
            field=models.CharField(blank=True, editable=False, max_length=64, null=True, unique=True),
        ),

        # 2. Cambiar curp de CharField(unique=True) a EncryptedCharField (sin unique)
        migrations.AlterField(
            model_name='user',
            name='curp',
            field=accounts.fields.EncryptedCharField(
                blank=True,
                max_length=18,
                null=True,
                validators=[
                    django.core.validators.RegexValidator(
                        code='curp_invalida',
                        message='El formato de CURP no es válido.',
                        regex=(
                            r'^[A-Z]{4}\d{6}[HM]'
                            r'(AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)'
                            r'[B-DF-HJ-NP-TV-Z]{3}[A-Z0-9]\d$'
                        ),
                    )
                ],
            ),
        ),

        # 3. Cifrar campos de UserAddress
        migrations.AlterField(
            model_name='useraddress',
            name='address',
            field=accounts.fields.EncryptedCharField(help_text='Calle y número', max_length=255),
        ),
        migrations.AlterField(
            model_name='useraddress',
            name='city',
            field=accounts.fields.EncryptedCharField(help_text='Ciudad', max_length=100),
        ),
        migrations.AlterField(
            model_name='useraddress',
            name='zip_code',
            field=accounts.fields.EncryptedCharField(help_text='Código postal', max_length=10),
        ),
    ]
