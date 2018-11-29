import binascii
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MinLengthValidator
from django.db import models

from core.models import UserCreatedModelMixin
from repocache.exceptions import RepoCacheMiss

from .repository import Repository


VISIBILITY_NOTE_PREFIX = 'Visibility: '


class Entity(UserCreatedModelMixin, models.Model):
    ENTITY_TYPE_MODEL = 'model'
    ENTITY_TYPE_PROTOCOL = 'protocol'
    ENTITY_TYPE_CHOICES = (
        (ENTITY_TYPE_MODEL, ENTITY_TYPE_MODEL),
        (ENTITY_TYPE_PROTOCOL, ENTITY_TYPE_PROTOCOL),
    )

    entity_type = models.CharField(
        max_length=16,
        choices=ENTITY_TYPE_CHOICES,
    )

    name = models.CharField(validators=[MinLengthValidator(2)], max_length=255)

    class Meta:
        ordering = ['name']
        unique_together = ('entity_type', 'name', 'author')
        permissions = (
            ('create_model', 'Can create models'),
            ('create_protocol', 'Can create protocols'),
        )

    def __str__(self):
        return self.name

    @property
    def repo(self):
        """This entity's git repository wrapper.

        Note that we do not cache this property as this can lead to too many open files.
        See also https://gitpython.readthedocs.io/en/stable/intro.html#leakage-of-system-resources
        """
        return Repository(self.repo_abs_path)

    @property
    def repo_abs_path(self):
        """
        Absolute filesystem path for this entity's repository

        :return: `Path` object
        """
        return Path(
            settings.REPO_BASE, str(self.author.id), '%ss' % self.entity_type, str(self.id)
        )

    def nice_version(self, commit):
        version = self.repo.get_name_for_commit(commit)
        if len(version) > 20:
            version = version[:8] + '...'
        return version

    def get_visibility_from_repo(self, commit):
        """
        Get the visibility of the given entity version from the repository

        :param commit: `repository.Commit` object
        :return visibility: string representing visibility
        """
        note = commit.get_note()
        if note and note.startswith(VISIBILITY_NOTE_PREFIX):
            return note[len(VISIBILITY_NOTE_PREFIX):]

    def set_visibility_in_repo(self, commit, visibility):
        """
        Set the visibility of the given entity version in the repository

        :param commit:`repository.Commit` object
        :param visibility: string representing visibility
        """
        commit.add_note('%s%s' % (VISIBILITY_NOTE_PREFIX, visibility))

    @property
    def repocache(self):
        from repocache.models import CachedEntity
        return CachedEntity.objects.get_or_create(entity=self)[0]

    def set_version_visibility(self, commit, visibility):
        """
        Set the visibility of the given entity version

        Updates both the repository and the cache

        :param commit: ref of the relevant commit
        :param visibility: string representing visibility
        """
        commit = self.repo.get_commit(commit)
        self.set_visibility_in_repo(commit, visibility)

        self.repocache.get_version(commit.hexsha).set_visibility(visibility)

    def get_version_visibility(self, sha, default=None):
        """
        Get the visibility of the given entity version

        This is fetched from the repocache

        :param sha: SHA of the relevant commit
        :param default: Default visibility if no entry found - defaults to `None`

        :return: string representing visibility
        :raise: RepoCacheMiss if entry not found and no default set
        """
        try:
            return self.repocache.get_version(sha).visibility
        except RepoCacheMiss:
            if default is not None:
                return default
            else:
                raise

    @staticmethod
    def _is_valid_sha(ref):
        if len(ref) == 40:
            try:
                binascii.unhexlify(ref)
                return True
            except binascii.Error:
                return False

        return False

    def get_ref_version_visibility(self, ref):
        """
        Get the visibility of the given entity version, with ref lookup

        :param ref: ref of the relevant commit (SHA, tag or 'latest')
        """
        if ref == 'latest':
            return self.repocache.visibility

        if self._is_valid_sha(ref):
            return self.get_version_visibility(ref)

        try:
            return self.repocache.tags.get(tag=ref).version.visibility
        except ObjectDoesNotExist:
            raise RepoCacheMiss("Entity version not found")

    def add_tag(self, tagname, ref):
        """
        Add a tag for the given entity version

        Updates both the repository and the cache

        :param tagname: Name of tag
        :param ref: ref of the relevant commit
        """
        commit = self.repo.get_commit(ref)
        self.repo.tag(tagname, ref=ref)
        try:
            self.repocache.get_version(commit.hexsha).tag(tagname)
        except RepoCacheMiss:
            pass

    @property
    def visibility(self):
        """
        Get the visibility of an entity

        This is fetched from the repocache

        :return: string representing visibility,
            or 'private' if visibility not available
        """
        return self.repocache.visibility

    def get_tags(self, sha):
        """
        Get the tags for the given entity version

        This is fetched from the repocache.

        :param sha: SHA of the relevant commit
        :return: set of tag names for the commit
        """
        return set(self.repocache.get_version(sha).tags.values_list('tag', flat=True))


class EntityManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(entity_type=self.model.entity_type)

    def create(self, **kwargs):
        kwargs['entity_type'] = self.model.entity_type
        return super().create(**kwargs)


class ModelEntity(Entity):
    entity_type = Entity.ENTITY_TYPE_MODEL
    other_type = Entity.ENTITY_TYPE_PROTOCOL

    objects = EntityManager()

    class Meta:
        proxy = True
        verbose_name_plural = 'Model entities'


class ProtocolEntity(Entity):
    entity_type = Entity.ENTITY_TYPE_PROTOCOL
    other_type = Entity.ENTITY_TYPE_MODEL

    objects = EntityManager()

    class Meta:
        proxy = True
        verbose_name_plural = 'Protocol entities'


class EntityFile(models.Model):
    entity = models.ForeignKey(Entity, related_name='files')
    upload = models.FileField(upload_to='uploads')
    original_name = models.CharField(max_length=255)

    def __str__(self):
        return self.original_name
