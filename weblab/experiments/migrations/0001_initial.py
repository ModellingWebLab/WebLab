# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-03-23 14:51
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('entities', '0007_auto_20180126_0837'),
    ]

    operations = [
        migrations.CreateModel(
            name='Experiment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creation_date', models.DateTimeField(auto_now_add=True)),
                ('visibility', models.CharField(choices=[('private', 'Private'), ('restricted', 'Restricted'), ('public', 'Public')], help_text='Public = anyone can view<br />Restricted = logged in users can view<br />Private = only you can view', max_length=16)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('model', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='model_experiments', to='entities.ModelEntity')),
                ('protocol', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='protocol_experiments', to='entities.ProtocolEntity')),
            ],
            options={
                'verbose_name_plural': 'Experiments',
                'permissions': (('create_experiment', 'Can create experiments'),),
            },
        ),
        migrations.AlterUniqueTogether(
            name='experiment',
            unique_together=set([('model', 'protocol')]),
        ),
    ]
