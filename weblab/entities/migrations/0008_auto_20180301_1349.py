# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-03-01 13:49
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('entities', '0007_auto_20180126_0837'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExperimentEntity',
            fields=[
            ],
            options={
                'proxy': True,
                'verbose_name_plural': 'Experiment entities',
                'indexes': [],
            },
            bases=('entities.entity',),
        ),
        migrations.AlterField(
            model_name='entity',
            name='entity_type',
            field=models.CharField(choices=[('model', 'model'), ('protocol', 'protocol'), ('experiment', 'experiment')], max_length=16),
        ),
        migrations.CreateModel(
            name='Experiment',
            fields=[
                ('entity', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='experiment', serialize=False, to='entities.ExperimentEntity')),
                ('model', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='model_experiments', to='entities.ModelEntity')),
                ('protocol', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='protocol_experiments', to='entities.ProtocolEntity')),
            ],
            options={
                'verbose_name_plural': 'Experiments',
            },
        ),
        migrations.AlterUniqueTogether(
            name='experiment',
            unique_together=set([('model', 'protocol')]),
        ),
    ]
