from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from core.models import VisibilityModelMixin
from core.visibility import Visibility
from entities.models import Entity

from .exceptions import RepoCacheMiss


class CachedEntity(models.Model):
    """
    Cache for an entity's repository.

    This is intended to reflect the state of the entity's repository,
    and should not be changed without first changing the repo.
    """
    entity = models.OneToOneField(Entity)

    @property
    def visibility(self):
        """
        Visibility of the entity (this is based on the visibility of the latest
        version)

        :return: string representing visibility, or PRIVATE if no versions found
        """
        try:
            return self.versions.latest().visibility
        except ObjectDoesNotExist:
            return Visibility.PRIVATE

    def get_version(self, sha):
        """
        Get a version of the entity

        :param sha: hex string of the commit SHA of the version

        :return: CachedEntityVersion object
        :raise: RepoCacheMiss if entity does not exist in cache, or has no versions
        """
        try:
            return self.versions.get(sha=sha)
        except ObjectDoesNotExist:
            raise RepoCacheMiss("Entity version not found")

    def add_version(self, sha):
        """
        Add an entity version to the cache

        :param sha: hex string of the commit SHA of the version
        :return CachedEntityVersion object
        """
        commit = self.entity.repo.get_commit(sha)
        visibility = self.entity.get_visibility_from_repo(commit)
        return CachedEntityVersion.objects.create(
            entity=self,
            sha=commit.hexsha,
            timestamp=commit.committed_at,
            visibility=visibility,
        )


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

    def set_visibility(self, visibility):
        """
        Set the visibility of this version, if it exists

        :param visibility: string representing visibility
        """
        self.visibility = visibility
        self.save()


class CachedEntityTag(models.Model):
    """
    Cache for a tag in an entity's repository
    """
    entity = models.ForeignKey(CachedEntity, related_name='tags')
    tag = models.CharField(max_length=255)
    version = models.ForeignKey(CachedEntityVersion)

    class Meta:
        unique_together = ['entity', 'tag']
