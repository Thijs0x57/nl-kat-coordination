# Generated by Django 4.2.7 on 2024-01-17 16:30

import django.db.models.deletion
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("account", "0003_alter_katuser_full_name")]

    operations = [
        migrations.CreateModel(
            name="AuthToken",
            fields=[
                ("digest", models.CharField(max_length=128, primary_key=True, serialize=False)),
                ("token_key", models.CharField(db_index=True, max_length=25)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("expiry", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=150, verbose_name="name")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="auth_token_set",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="authtoken",
            constraint=models.UniqueConstraint(
                models.F("user"), django.db.models.functions.text.Lower("name"), name="unique name"
            ),
        ),
    ]
