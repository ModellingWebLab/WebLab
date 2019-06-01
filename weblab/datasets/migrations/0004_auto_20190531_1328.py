# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-31 12:28
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0003_experimentaldataset_description'),
    ]

    operations = [
        migrations.AlterField(
            model_name='datasetfile',
            name='dataset',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='file_uploads', to='datasets.ExperimentalDataset'),
        ),
    ]