# Generated by Django 2.2.16 on 2021-10-01 16:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0017_graph'),
    ]

    operations = [
        migrations.AddField(
            model_name='graph',
            name='order',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
    ]
