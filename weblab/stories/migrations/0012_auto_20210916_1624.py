# Generated by Django 2.2.16 on 2021-09-16 16:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stories', '0011_auto_20210916_1617'),
    ]

    operations = [
        migrations.AddField(
            model_name='storypart',
            name='order',
            field=models.IntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AlterOrderWithRespectTo(
            name='storypart',
            order_with_respect_to=None,
        ),
    ]