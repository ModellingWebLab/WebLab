from pathlib import Path

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Q
from django.utils.functional import cached_property

from .repository import Repository


class Entity(models.Model):
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_RESTRICTED = 'restricted'
    VISIBILITY_PUBLIC = 'public'

    VISIBILITY_CHOICES = (
        (VISIBILITY_PRIVATE, 'Private'),
        (VISIBILITY_RESTRICTED, 'Restricted'),
        (VISIBILITY_PUBLIC, 'Public')
    )
    VISIBILITY_HELP = (
        'Public = anyone can view\n'
        'Restricted = logged in users can view\n'
        'Private = only you can view'
    )

    ENTITY_TYPE_MODEL = 'model'
    ENTITY_TYPE_PROTOCOL = 'protocol'
    ENTITY_TYPE_EXPERIMENT = 'experiment'
    ENTITY_TYPE_CHOICES = (
        (ENTITY_TYPE_MODEL, ENTITY_TYPE_MODEL),
        (ENTITY_TYPE_PROTOCOL, ENTITY_TYPE_PROTOCOL),
        (ENTITY_TYPE_EXPERIMENT, ENTITY_TYPE_EXPERIMENT),
    )

    entity_type = models.CharField(
        max_length=16,
        choices=ENTITY_TYPE_CHOICES,
    )

    name = models.CharField(validators=[MinLengthValidator(2)], max_length=255)
    creation_date = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL)
    visibility = models.CharField(
        max_length=16,
        choices=VISIBILITY_CHOICES,
        help_text=VISIBILITY_HELP.replace('\n', '<br />'),
    )

    class Meta:
        ordering = ['name']
        unique_together = ('entity_type', 'name', 'author')
        permissions = (
            ('create_model', 'Can create models'),
            ('create_protocol', 'Can create protocols'),
            ('create_experiment', 'Can create experiments'),
            ('create_model_version', 'Can create new versions of a model'),
            ('create_protocol_version', 'Can create new versions of a protocol'),
        )

    def __str__(self):
        return self.name

    def is_deletable_by(self, user):
        """
        Is the entity deletable by the given user?

        :param user: User object
        :return: True if deletable, False otherwise
        """
        return user.is_superuser or user == self.author

    @cached_property
    def repo(self):
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


class EntityManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(entity_type=self.model.entity_type)

    def visible_to_user(self, user):
        return self.get_queryset().filter(Q(author=user) | ~Q(visibility=Entity.VISIBILITY_PRIVATE))

    def create(self, **kwargs):
        kwargs['entity_type'] = self.model.entity_type
        return super().create(**kwargs)


class ModelEntity(Entity):
    entity_type = Entity.ENTITY_TYPE_MODEL

    objects = EntityManager()

    class Meta:
        proxy = True
        verbose_name_plural = 'Model entities'


class ProtocolEntity(Entity):
    entity_type = Entity.ENTITY_TYPE_PROTOCOL

    objects = EntityManager()

    class Meta:
        proxy = True
        verbose_name_plural = 'Protocol entities'


class ExperimentEntity(Entity):
    entity_type = Entity.ENTITY_TYPE_EXPERIMENT

    objects = EntityManager()

    class Meta:
        proxy = True
        verbose_name_plural = 'Experiment entities'


class Experiment(models.Model):
    """
    Stores extra fields related to Experiment

    (since all Entity objects are stored in the same table,
    experiment-specific fields and their constraints are best stored separately)
    """
    entity = models.OneToOneField(
        ExperimentEntity,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='experiment'
    )

    model = models.ForeignKey(ModelEntity, related_name='model_experiments')
    protocol = models.ForeignKey(ProtocolEntity, related_name='protocol_experiments')

    class Meta:
        unique_together = ('model', 'protocol')
        verbose_name_plural = 'Experiments'


class EntityFile(models.Model):
    entity = models.ForeignKey(Entity, related_name='files')
    upload = models.FileField(upload_to='uploads')
    original_name = models.CharField(max_length=255)

    def __str__(self):
        return self.original_name
