from pathlib import Path

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models

from core.models import UserCreatedModelMixin
from core.visibility import Visibility
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
            ('create_model_version', 'Can create new versions of a model'),
            ('create_protocol_version', 'Can create new versions of a protocol'),
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

    def set_version_visibility(self, commit, visibility):
        """
        Set the visibility of the given entity version

        :param commit: ref of the relevant commit
        :param visibility: string representing visibility
        """
        self.repo.get_commit(commit).add_note(
            '%s%s' % (VISIBILITY_NOTE_PREFIX, visibility))

    def get_version_visibility(self, commit):
        """
        Get the visibility of the given entity version

        Will backtrack through previous visibilities, defaulting to entity
        visibility if none is found, and forward apply these as repository
        notes for future access.

        :param commit: ref of the relevant commit
        :return: string representing visibility
        """
        vis = Visibility.PRIVATE

        from repocache.entities import get_version_visibility
        try:
            return get_version_visibility(self, commit)
        except RepoCacheMiss:
            # continue and fetch visibility directly from repo
            pass

        commit = self.repo.get_commit(commit)
        if not commit:
            return vis

        # If this commit does not have a visibility, backtrack through history
        # until we find one.
        no_visibility = []
        for commit_ in commit.self_and_parents:
            note = commit_.get_note()
            if note and note.startswith(VISIBILITY_NOTE_PREFIX):
                vis = note[len(VISIBILITY_NOTE_PREFIX):]
                break
            else:
                no_visibility.append(commit_)

        # Apply visibility to newer versions which were found without one
        for commit_ in no_visibility:
            self.set_version_visibility(commit_.hexsha, vis)

        return vis

    @property
    def visibility(self):
        # Look in the cache
        from repocache.entities import get_visibility
        try:
            return get_visibility(self)
        except RepoCacheMiss:
            commit = self.repo.latest_commit
            if commit:
                return self.get_version_visibility(commit.hexsha)
            else:
                return Visibility.PRIVATE


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
