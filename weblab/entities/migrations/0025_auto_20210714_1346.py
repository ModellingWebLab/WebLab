# Generated by Django 2.2.16 on 2021-07-14 13:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('entities', '0024_auto_20210714_1245'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='modelgroup',
            options={'ordering': ['title'], 'permissions': (('edit_entity', 'Can edit modelgroup'),)},
        ),
    ]
