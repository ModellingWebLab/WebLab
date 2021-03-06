# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-02-18 15:13
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('entities', '0012_auto_20190111_1705'),
        ('experiments', '0017_auto_20180529_1353'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlannedExperiment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model_version', models.CharField(max_length=50)),
                ('protocol_version', models.CharField(max_length=50)),
                ('model', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='planned_model_experiments', to='entities.ModelEntity')),
                ('protocol', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='planned_protocol_experiments', to='entities.ProtocolEntity')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='plannedexperiment',
            unique_together=set([('model', 'protocol', 'model_version', 'protocol_version')]),
        ),
    ]
