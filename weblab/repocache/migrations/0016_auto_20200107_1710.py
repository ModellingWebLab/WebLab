# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2020-01-07 17:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repocache', '0015_auto_20191128_1331'),
    ]

    operations = [
        migrations.AddField(
            model_name='cachedmodelversion',
            name='master_filename',
            field=models.TextField(default=' ', help_text='Master filename'),
        ),
        migrations.AddField(
            model_name='cachedprotocolversion',
            name='master_filename',
            field=models.TextField(default=' ', help_text='Master filename'),
        ),
    ]
