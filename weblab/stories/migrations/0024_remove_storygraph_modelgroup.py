# Generated by Django 2.2.16 on 2021-10-08 16:41

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0023_storygraph_modelgroup'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='storygraph',
            name='modelgroup',
        ),
    ]
