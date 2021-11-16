# Generated by Django 2.2.24 on 2021-11-04 17:08

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    replaces = [('entities', '0019_modelgroup'), ('entities', '0020_auto_20210708_1240'), ('entities', '0021_modelgroup_visibility'), ('entities', '0022_auto_20210713_1530'), ('entities', '0023_auto_20210713_1541'), ('entities', '0024_auto_20210714_1245'), ('entities', '0025_auto_20210714_1346'), ('entities', '0026_auto_20210716_0940'), ('entities', '0027_auto_20210716_1000'), ('entities', '0028_auto_20210716_1003'), ('entities', '0029_auto_20210721_0930'), ('entities', '0030_story'), ('entities', '0031_story_models'), ('entities', '0032_auto_20210824_1329'), ('entities', '0033_auto_20210824_1330'), ('entities', '0034_auto_20210831_1332'), ('entities', '0035_delete_story')]

    dependencies = [
        ('entities', '0018_auto_20201201_1115'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ModelGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('models', models.ManyToManyField(to='entities.ModelEntity')),
                ('author', models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('created_at', models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now)),
                ('visibility', models.CharField(choices=[('private', 'Private'), ('public', 'Public'), ('moderated', 'Moderated')], default='Private', help_text='Moderated = public and checked by a moderator<br />Public = anyone can view<br />Private = only you can view', max_length=16)),
            ],
            options={
                'ordering': ['title'],
                'unique_together': {('title', 'author')},
                'permissions': (('edit_modelgroup', 'Can edit modelgroup'),),
            },
        ),
    ]