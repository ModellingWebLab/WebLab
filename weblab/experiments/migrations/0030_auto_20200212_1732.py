# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2020-02-12 17:32
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('experiments', '0029_auto_20200212_1731'),
    ]

    operations = [
        migrations.AlterField(
            model_name='runnable',
            name='experiment',
            field=models.ForeignKey(db_constraint=False, db_index=False, on_delete=django.db.models.deletion.CASCADE, to='experiments.Experiment'),
        ),
    ]