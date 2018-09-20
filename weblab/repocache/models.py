from django.db import models

from core.models import VisibilityModelMixin
from entities.models import Entity


class CachedEntity(models.Model):
    entity = models.OneToOneField(Entity)
    latest_version = models.OneToOneField('CachedEntityVersion', null=True)


class CachedEntityVersion(VisibilityModelMixin):
    entity = models.ForeignKey(CachedEntity, related_name='versions')
    sha = models.CharField(max_length=40)

    # Visibility is the only value we need to store for now

    class Meta:
        unique_together = ['entity', 'sha']


class CachedEntityTag(models.Model):
    entity = models.ForeignKey(CachedEntity, related_name='tags')
    tag = models.CharField(max_length=255)
    version = models.ForeignKey(CachedEntityVersion)

    class Meta:
        unique_together = ['entity', 'tag']
