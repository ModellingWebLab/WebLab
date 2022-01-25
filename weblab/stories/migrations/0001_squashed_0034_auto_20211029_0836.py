# Generated by Django 2.2.24 on 2021-11-04 16:54

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    replaces = [('stories', '0001_initial'), ('stories', '0002_story_experiments'), ('stories', '0003_storytext'), ('stories', '0004_auto_20210907_1553'), ('stories', '0005_auto_20210907_1723'), ('stories', '0006_simplestory'), ('stories', '0007_remove_simplestory_description'), ('stories', '0008_storypart'), ('stories', '0009_auto_20210915_1105'), ('stories', '0010_auto_20210916_1549'), ('stories', '0011_auto_20210916_1617'), ('stories', '0012_auto_20210916_1624'), ('stories', '0013_auto_20210922_1513'), ('stories', '0014_auto_20210922_1514'), ('stories', '0015_delete_simplestory'), ('stories', '0016_remove_story_description'), ('stories', '0017_graph'), ('stories', '0018_graph_order'), ('stories', '0019_auto_20211001_1635'), ('stories', '0020_auto_20211001_1636'), ('stories', '0021_auto_20211001_1641'), ('stories', '0022_auto_20211007_1416'), ('stories', '0023_storygraph_modelgroup'), ('stories', '0024_remove_storygraph_modelgroup'), ('stories', '0025_storygraph_modelgroup'), ('stories', '0026_auto_20211008_1714'), ('stories', '0027_remove_storygraph_modelgroup'), ('stories', '0028_storygraph_modelgroup'), ('stories', '0029_auto_20211008_1730'), ('stories', '0030_storygraph_graphvisualiser'), ('stories', '0031_auto_20211028_0911'), ('stories', '0032_auto_20211028_0913'), ('stories', '0033_auto_20211028_0918'), ('stories', '0034_auto_20211029_0836')]

    initial = True

    dependencies = [
        ('experiments', '0032_auto_20200317_0927'),
        ('entities', '0035_delete_story'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Story',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visibility', models.CharField(choices=[('private', 'Private'), ('public', 'Public'), ('moderated', 'Moderated')], help_text='Moderated = public and checked by a moderator<br />Public = anyone can view<br />Private = only you can view', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('title', models.CharField(max_length=255)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('graphvisualizer', models.CharField(choices=[('displayPlotFlot', 'displayPlotFlot'), ('displayPlotHC', 'displayPlotHC')], default='displayPlotFlot', help_text='The different visualisers determine how graphs are shown in this story.', max_length=16)),
            ],
            options={
                'ordering': ['title'],
                'permissions': (('edit_story', 'Can edit story'),),
                'unique_together': {('title', 'author')},
            },
        ),
        migrations.CreateModel(
            name='StoryItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.IntegerField()),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('story', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='stories.Story')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='StoryText',
            fields=[
                ('description', models.TextField(blank=True, default='')),
                ('storyitem_ptr', models.OneToOneField(auto_created=True, default=0, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='stories.StoryItem')),
            ],
            options={
                'order_with_respect_to': None,
            },
        ),
        migrations.CreateModel(
            name='StoryGraph',
            fields=[
                ('graphfilename', models.TextField()),
                ('cachedmodelversions', models.ManyToManyField(to='repocache.CachedModelVersion')),
                ('cachedprotocolversion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='protocolforgraph', to='repocache.CachedProtocolVersion')),
                ('storyitem_ptr', models.OneToOneField(auto_created=True, default=0, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='stories.StoryItem')),
                ('modelgroup', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_DEFAULT, to='entities.ModelGroup')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]