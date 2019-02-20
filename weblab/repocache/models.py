from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from core.models import VisibilityModelMixin
from entities.models import Entity

from .exceptions import RepoCacheMiss


class CachedEntity(models.Model):
    """
    Cache for an entity's repository.

    This is intended to reflect the state of the entity's repository,
    and should not be changed without first changing the repo.
    """
    entity = models.OneToOneField(Entity, on_delete=models.CASCADE)

    @property
    def visibility(self):
        """
        Visibility of the entity (this is based on the visibility of the latest
        version)

        :return: string representing visibility, or PRIVATE if no versions found
        """
        try:
            return self.latest_version.visibility
        except ObjectDoesNotExist:
            return Entity.DEFAULT_VISIBILITY

    @property
    def latest_version(self):
        return self.versions.latest()

    def get_version(self, sha):
        """
        Get a version of the entity

        :param sha: hex string of the commit SHA of the version
            or 'latest' to get the latest version

        :return: CachedEntityVersion object
        :raise: RepoCacheMiss if entity does not exist in cache, or has no versions
        """
        try:
            if sha == 'latest':
                return self.latest_version
            else:
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
    entity = models.ForeignKey(CachedEntity, on_delete=models.CASCADE, related_name='versions')
    sha = models.CharField(max_length=40)
    timestamp = models.DateTimeField()

    class Meta:
        unique_together = ['entity', 'sha']
        get_latest_by = 'timestamp'
        ordering = ['-timestamp', '-pk']

    def set_visibility(self, visibility):
        """
        Set the visibility of this version, if it exists

        :param visibility: string representing visibility
        """
        self.visibility = visibility
        self.save()

    def tag(self, tagname):
        """
        Add a tag for this version

        :param tagname: Tag name
        """
        return CachedEntityTag.objects.create(
            entity=self.entity,
            version=self,
            tag=tagname,
        )


class CachedEntityTag(models.Model):
    """
    Cache for a tag in an entity's repository
    """
    entity = models.ForeignKey(CachedEntity, related_name='tags')
    tag = models.CharField(max_length=255)
    version = models.ForeignKey(CachedEntityVersion, on_delete=models.CASCADE, related_name='tags')

    class Meta:
        unique_together = ['entity', 'tag']


class ProtocolInterface(models.Model):
    """
    A record of the ontology terms comprising a protocol's interface with models.

    Eventually this will be stored in a proper RDF triple store rather than in the DB.

    A blank term is added to indicate that the interface has been analysed, in case of no actual terms being found.
    """
    protocol_version = models.ForeignKey(CachedEntityVersion, on_delete=models.CASCADE, related_name='interface')
    term = models.CharField(
        max_length=500,
        blank=True,
        help_text='an ontology term in the interface')
    optional = models.BooleanField(help_text='whether this term is required to be present in models')

    class Meta:
        unique_together = ['protocol_version', 'term']
