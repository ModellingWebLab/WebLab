# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-10-12 13:37
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('repocache', '0002_cachedentityversion_timestamp'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='cachedentityversion',
            options={'get_latest_by': 'timestamp'},
        ),
        migrations.RemoveField(
            model_name='cachedentity',
            name='latest_version',
        ),
    ]
