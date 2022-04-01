# Generated by Django 2.2.24 on 2022-01-25 21:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiments', '0032_auto_20200317_0927'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='experiment',
            index=models.Index(fields=['model_version', 'protocol_version'], name='experiments_model_v_5efcd4_idx'),
        ),
    ]
