# Generated by Django 5.0.8 on 2024-09-04 13:03

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0001_squashed_0004_authtoken_authtoken_unique_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="katuser",
            name="clearance_level",
            field=models.IntegerField(
                default=-1,
                help_text="The clearance level of the user for all organizations.",
                validators=[django.core.validators.MinValueValidator(-1), django.core.validators.MaxValueValidator(4)],
            ),
        ),
    ]
