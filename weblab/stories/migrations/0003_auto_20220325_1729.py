# Generated by Django 2.2.27 on 2022-03-25 17:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0002_auto_20220125_1459'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storygraph',
            name='graphfilename',
            field=models.TextField(null=True),
        ),
    ]
