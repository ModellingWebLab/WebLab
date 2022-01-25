# Generated by Django 2.2.24 on 2022-01-25 14:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0007_auto_20201201_1115'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='visibility',
            field=models.CharField(choices=[('private', 'Private'), ('public', 'Public'), ('moderated', 'Moderated')], help_text='Moderated = public and checked by a moderator<br />Public = anyone can view<br />Private = only you can view', max_length=16),
        ),
    ]