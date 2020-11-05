# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-11-05 14:55
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('repocache', '0023_auto_20201001_1358'),
        ('datasets', '0005_auto_20190628_1253'),
    ]

    operations = [
        migrations.CreateModel(
            name='DatasetColumnMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('column_name', models.CharField(help_text='name of the column', max_length=200)),
                ('column_units', models.CharField(blank=True, help_text='units of the column, as a pint definition string', max_length=200)),
                ('dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='column_mappings', to='datasets.Dataset')),
                ('protocol_ioput', models.ForeignKey(help_text='Protocol input or output to link to', null=True, on_delete=django.db.models.deletion.CASCADE, to='repocache.ProtocolIoputs')),
                ('protocol_version', models.ForeignKey(help_text='Protocol version to link to', on_delete=django.db.models.deletion.CASCADE, to='repocache.CachedProtocolVersion')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='datasetcolumnmapping',
            unique_together=set([('dataset', 'column_name', 'protocol_version')]),
        ),
    ]
