# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-04-08 12:05
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repocache', '0008_auto_20190218_1513'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cachedentityversion',
            name='visibility',
            field=models.CharField(choices=[('private', 'Private'), ('public', 'Public'), ('moderated', 'Moderated')], help_text='Public = anyone can view<br />Private = only you can view', max_length=16),
        ),
    ]
