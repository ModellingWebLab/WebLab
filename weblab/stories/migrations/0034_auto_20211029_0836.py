# Generated by Django 2.2.24 on 2021-10-29 08:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0033_auto_20211028_0918'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storyitem',
            name='story',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='stories.Story'),
        ),
    ]
