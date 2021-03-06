# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2020-01-31 16:12
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('experiments', '0018_auto_20190218_1513'),
    ]

    operations = [
        migrations.AddField(
            model_name='plannedexperiment',
            name='submitter',
            field=models.ForeignKey(default=None, help_text='the user that requested this experiment', null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddIndex(
            model_name='plannedexperiment',
            index=models.Index(fields=['submitter'], name='experiments_submitt_e57544_idx'),
        ),
    ]
