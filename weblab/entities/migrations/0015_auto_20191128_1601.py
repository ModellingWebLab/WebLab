# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-11-28 16:01
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('entities', '0014_entity_is_fitting_spec'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='entity',
            options={'ordering': ['name'], 'permissions': (('create_model', 'Can create models'), ('create_protocol', 'Can create protocols'), ('create_fittingspec', 'Can create fitting specifications'), ('edit_entity', 'Can edit entity'), ('moderator', 'Can promote public entity versions to moderated'))},
        ),
        migrations.AlterField(
            model_name='entity',
            name='entity_type',
            field=models.CharField(choices=[('model', 'model'), ('protocol', 'protocol'), ('fittingspec', 'fittingspec')], max_length=16),
        ),
    ]