# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-05-23 13:06
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('experiments', '0009_auto_20180517_1300'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='experiment',
            options={'permissions': (('create_experiment', 'Can create experiments'),), 'verbose_name_plural': 'Experiments'},
        ),
    ]
