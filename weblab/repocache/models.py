from django.db import models

from core.models import VisibilityModelMixin
from entities.models import Entity


class CachedEntity(models.Model):
    """
    Cache for an entity's repository.

    This is intended to reflect the state of the entity's repository,
    and should not be changed without first changing the repo.
    """
    entity = models.OneToOneField(Entity)


class CachedEntityVersion(VisibilityModelMixin):
    """
    Cache for a single version / commit in an entity's repository
    """
    entity = models.ForeignKey(CachedEntity, related_name='versions')
    sha = models.CharField(max_length=40)
    timestamp = models.DateTimeField()

    class Meta:
        unique_together = ['entity', 'sha']
        get_latest_by = 'timestamp'


class CachedEntityTag(models.Model):
    """
    Cache for a tag in an entity's repository
    """
    entity = models.ForeignKey(CachedEntity, related_name='tags')
    tag = models.CharField(max_length=255)
    version = models.ForeignKey(CachedEntityVersion)

    class Meta:
        unique_together = ['entity', 'tag']
