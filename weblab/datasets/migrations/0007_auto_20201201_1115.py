# Generated by Django 2.2.16 on 2020-12-01 11:15

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0006_auto_20201105_1455'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='dataset',
            options={'ordering': ['name'], 'permissions': (('create_dataset', 'Can create experimental datasets'), ('edit_entity', 'Can edit entity')), 'verbose_name_plural': 'Datasets'},
        ),
    ]