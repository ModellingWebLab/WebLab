# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2020-01-15 10:45
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repocache', '0017_auto_20200115_1011'),
    ]

    operations = [
        migrations.AddField(
            model_name='cachedmodelversion',
            name='author',
            field=models.TextField(default=' ', help_text='Author full name'),
        ),
        migrations.AddField(
            model_name='cachedprotocolversion',
            name='author',
            field=models.TextField(default=' ', help_text='Author full name'),
        ),
    ]
