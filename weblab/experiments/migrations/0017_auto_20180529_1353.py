# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-05-29 13:53
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiments', '0016_auto_20180529_1349'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='experimentversion',
            name='task_id',
        ),
        migrations.AlterField(
            model_name='runningexperiment',
            name='task_id',
            field=models.CharField(max_length=50),
        ),
    ]