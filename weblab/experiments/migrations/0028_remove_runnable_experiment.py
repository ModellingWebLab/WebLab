# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2020-02-13 10:19
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('experiments', '0027_move_runnable'),
    ]

    operations = [

        migrations.RemoveField(
            model_name='runnable',
            name='experiment',
        ),
    ]
