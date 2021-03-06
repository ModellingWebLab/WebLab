# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2020-02-04 10:56
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    def populate_fks(apps, schema_editor):
        Experiment = apps.get_model('experiments', 'Experiment')
        for experiment in Experiment.objects.all():
            experiment.model_version_fk = experiment.model.cachedmodel.versions.get(sha=experiment.model_version)
            experiment.protocol_version_fk = experiment.protocol.cachedprotocol.versions.get(sha=experiment.protocol_version)
            experiment.save()

    def remove_fks(apps, schema_editor):
        Experiment = apps.get_model('experiments', 'Experiment')
        for experiment in Experiment.objects.all():
            experiment.model_version_fk = None
            experiment.protocol_version_fk = None
            experiment.save()

    dependencies = [
        ('experiments', '0019_auto_20200204_1039'),
    ]

    operations = [
        migrations.RunPython(populate_fks, remove_fks),
    ]
