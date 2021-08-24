# Generated by Django 2.2.16 on 2021-08-24 13:25

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('entities', '0029_auto_20210721_0930'),
    ]

    operations = [
        migrations.CreateModel(
            name='Story',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visibility', models.CharField(choices=[('private', 'Private'), ('public', 'Public'), ('moderated', 'Moderated')], help_text='Moderated = public and checked by a moderator<br />Public = anyone can view<br />Private = only you can view', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(verbose_name='Description')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['title'],
                'permissions': (('edit_story', 'Can edit story'),),
                'unique_together': {('title', 'author')},
            },
        ),
    ]
