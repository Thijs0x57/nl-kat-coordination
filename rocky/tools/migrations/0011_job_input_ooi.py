# Generated by Django 3.2.5 on 2021-12-08 12:13

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tools", "0010_alter_scanprofile_reference")]

    operations = [migrations.AddField(model_name="job", name="input_ooi", field=models.TextField(null=True))]
