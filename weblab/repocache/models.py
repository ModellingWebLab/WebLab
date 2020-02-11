from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from core.models import VisibilityModelMixin
from core.visibility import Visibility
from entities.models import ModelEntity, ProtocolEntity
from fitting.models import FittingSpec

from .exceptions import RepoCacheMiss


####################################################################################################
#
# Base classes defining the common cache structure
#

class CachedEntity(models.Model):
    """
    Abstract class representing a cache for any entity type's repository.

    This is intended to reflect the state of the entity's repository,
    and should not be changed without first changing the repo.

    Concrete cache types should inherit from this and define a suitable ``entity`` column, e.g.
        entity = models.OneToOneField(ModelEntity, on_delete=models.CASCADE, related_name='cachedentity')

    Once a trio of (entity, version, tag) concrete cache classes are defined, the method
    _set_class_links() should be called to let them know about each other, setting the
    CachedModelClass, CachedVersionClass and CachedTagClass properties on each class.
    """

    class Meta:
        abstract = True

    @property
    def visibility(self):
        """
        Visibility of the entity (this is based on the most visible version).

        :return: string representing visibility, or PRIVATE if no versions found
        """
        if self.versions.filter(visibility=Visibility.MODERATED).exists():
            return Visibility.MODERATED
        if self.versions.filter(visibility=Visibility.PUBLIC).exists():
            return Visibility.PUBLIC
        return Visibility.PRIVATE

    @property
    def latest_version(self):
        return self.versions.latest()

    def get_version(self, sha):
        """
        Get a version of the entity

        :param sha: hex string of the commit SHA of the version,
            or 'latest' to get the latest version

        :return: CachedVersionClass object
        :raise: RepoCacheMiss if entity does not exist in cache, or has no versions
        """
        try:
            if sha == 'latest':
                return self.latest_version
            else:
                return self.versions.get(sha=sha)
        except ObjectDoesNotExist:
            try:
                return self.tags.get(tag=sha).version
            except ObjectDoesNotExist:
                raise RepoCacheMiss("Entity version not found")

    def get_name_for_version(self, sha):
        """Get a human-friendly display name for the given version

        :param sha: version sha
        :return: first cached tag for this version, if any, or sha if not
        """
        version = self.get_version(sha)
        if sha == 'latest' and version.tags.count() == 0:
            return 'latest'
        return version.get_name()

    def add_version(self, sha):
        """
        Add an entity version to the cache

        :param sha: hex string of the commit SHA of the version
        :return: CachedVersionClass object
        """
        commit = self.entity.repo.get_commit(sha)
        visibility = self.entity.get_visibility_from_repo(commit)
        return self.CachedVersionClass.objects.create(
            entity=self,
            sha=commit.sha,
            message=commit.message,
            master_filename=commit.master_filename,
            author=commit.author.name,
            numfiles=len(commit.filenames),
            timestamp=commit.timestamp,
            visibility=visibility,
        )


class CachedEntityVersion(VisibilityModelMixin):
    """
    Abstract class representing a cache for a single version / commit in any entity type's repository.

    Concrete cache types should inherit from this and define a suitable ``entity`` column, e.g.
        entity = models.ForeignKey(CachedModel, on_delete=models.CASCADE, related_name='versions')

    They should also define the property:
    - ``CachedTagClass`` referring to the concrete ``CachedEntityTagMixin`` they use
    """
    sha = models.CharField(max_length=40)
    timestamp = models.DateTimeField(help_text='When this commit was made')
    message = models.TextField(help_text='Git commit message', default=' ')
    master_filename = models.TextField(help_text='Master filename', default=None, null=True)
    # author is the committer of the version not the original author of the entity
    author = models.TextField(help_text='Author full name', default=' ')
    numfiles = models.IntegerField(blank=True, null=True)
    parsed_ok = models.BooleanField(
        default=False,
        help_text='Whether this entity version has been verified as syntactically correct'
    )

    class Meta:
        abstract = True
        unique_together = ['entity', 'sha']
        get_latest_by = 'timestamp'
        ordering = ['-timestamp', '-pk']

    def __str__(self):
        """Return handy representation for debugging."""
        return self.entity.entity.name + '@' + self.sha

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
        return self.CachedTagClass.objects.create(
            entity=self.entity,
            version=self,
            tag=tagname,
        )

    def get_name(self):
        """
        Get name for this version
        """
        first_tag = self.tags.first()
        if first_tag is not None:
            return first_tag.tag
        return self.sha

    def nice_version(self):
        """
        Returns tag/sha with ellipses

        :return version_name: string with the sha_or_tag formatted
        """
        version_name = self.get_name()
        if len(version_name) > 20:
            version_name = version_name[:8] + '...'
        return version_name

class CachedEntityTag(models.Model):
    """
    Abstract class representing a cache for a tag in any entity type's repository.

    Concrete cache types should inherit from this and define suitable ``entity`` and ``version``
    columns, e.g.
        entity = models.ForeignKey(CachedModel, related_name='tags')
        version = models.ForeignKey(CachedModelVersion, on_delete=models.CASCADE, related_name='tags')
    """
    tag = models.CharField(max_length=255)

    class Meta:
        abstract = True
        unique_together = ['entity', 'tag']


def _set_class_links(entity_cache_type, version_cache_type, tag_cache_type):
    """Set the CachedModelClass, CachedVersionClass and CachedTagClass property on each relevant class."""
    entity_cache_type.CachedVersionClass = version_cache_type
    entity_cache_type.CachedTagClass = tag_cache_type

    version_cache_type.CachedEntityClass = entity_cache_type
    version_cache_type.CachedTagClass = tag_cache_type

    tag_cache_type.CachedEntityClass = entity_cache_type
    tag_cache_type.CachedVersionClass = version_cache_type


####################################################################################################
#
# Concrete cache classes go here
#

class CachedModel(CachedEntity):
    """Cache for a CellML model's repository."""
    entity = models.OneToOneField(ModelEntity, on_delete=models.CASCADE, related_name='cachedmodel')


class CachedModelVersion(CachedEntityVersion):
    """Cache for a single version / commit in a CellML model's repository."""
    entity = models.ForeignKey(CachedModel, on_delete=models.CASCADE, related_name='versions')


class CachedModelTag(CachedEntityTag):
    """Cache for a tag in a CellML model's repository."""
    entity = models.ForeignKey(CachedModel, related_name='tags')
    version = models.ForeignKey(CachedModelVersion, on_delete=models.CASCADE, related_name='tags')


_set_class_links(CachedModel, CachedModelVersion, CachedModelTag)


class CachedProtocol(CachedEntity):
    """Cache for a protocol's repository."""
    entity = models.OneToOneField(ProtocolEntity, on_delete=models.CASCADE, related_name='cachedprotocol')


class CachedProtocolVersion(CachedEntityVersion):
    """Cache for a single version / commit in a protocol's repository."""
    entity = models.ForeignKey(CachedProtocol, on_delete=models.CASCADE, related_name='versions')


class CachedProtocolTag(CachedEntityTag):
    """Cache for a tag in a protocol's repository."""
    entity = models.ForeignKey(CachedProtocol, related_name='tags')
    version = models.ForeignKey(CachedProtocolVersion, on_delete=models.CASCADE, related_name='tags')


_set_class_links(CachedProtocol, CachedProtocolVersion, CachedProtocolTag)


class CachedFittingSpec(CachedEntity):
    """Cache for a fitting specifications's repository."""
    entity = models.OneToOneField(FittingSpec, on_delete=models.CASCADE, related_name='cachedfittingspec')


class CachedFittingSpecVersion(CachedEntityVersion):
    """Cache for a single version / commit in a fitting specifications's repository."""
    entity = models.ForeignKey(CachedFittingSpec, on_delete=models.CASCADE, related_name='versions')


class CachedFittingSpecTag(CachedEntityTag):
    """Cache for a tag in a fitting specifications's repository."""
    entity = models.ForeignKey(CachedFittingSpec, related_name='tags')
    version = models.ForeignKey(CachedFittingSpecVersion, on_delete=models.CASCADE, related_name='tags')


_set_class_links(CachedFittingSpec, CachedFittingSpecVersion, CachedFittingSpecTag)


CACHE_TYPE_MAP = {
    'model': CachedModel,
    'protocol': CachedProtocol,
    'fittingspec': CachedFittingSpec,
}

CACHED_VERSION_TYPE_MAP = {
    'model': CachedModelVersion,
    'protocol': CachedProtocolVersion,
    'fittingspec': CachedFittingSpecVersion,
}


def get_or_create_cached_entity(entity):
    """Return the appropriate concrete cache instance for a given entity."""
    cache_cls = CACHE_TYPE_MAP[entity.entity_type]
    return cache_cls.objects.get_or_create(entity=entity)


####################################################################################################
#
# Finally, we have other classes that build on the cache to store per-version information
#

class ProtocolInterface(models.Model):
    """
    A record of the ontology terms comprising a protocol's interface with models.

    Eventually this will be stored in a proper RDF triple store rather than in the DB.

    A blank term is added to indicate that the interface has been analysed, in case of no actual terms being found.
    """
    protocol_version = models.ForeignKey(CachedProtocolVersion, on_delete=models.CASCADE, related_name='interface')
    term = models.CharField(
        max_length=500,
        blank=True,
        help_text='an ontology term in the interface')
    optional = models.BooleanField(help_text='whether this term is required to be present in models')

    class Meta:
        unique_together = ['protocol_version', 'term']
