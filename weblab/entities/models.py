from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator
from django.db import models
from git import Repo


User = get_user_model()


class Entity(models.Model):
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_RESTRICTED = 'restricted'
    VISIBILITY_PUBLIC = 'public'

    VISIBILITY_CHOICES = (
        (VISIBILITY_PRIVATE, 'Private'),
        (VISIBILITY_RESTRICTED, 'Restricted'),
        (VISIBILITY_PUBLIC, 'Public')
    )

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
    creation_date = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User)
    visibility = models.CharField(
        max_length=16,
        choices=VISIBILITY_CHOICES,
        help_text=(
            'Public = anyone can view<br>'
            'Restricted = logged in users can view<br>'
            'Private = only you can view'
        ),
    )

    def init_repo(self):
        Repo.init(self.repo_abs_path)

    def add_file_to_repo(self, file_path):
        self.repo.index.add([file_path])

    def commit_repo(self, message):
        self.repo.index.commit(message)

    def tag_repo(self, tag):
        self.repo.create_tag(tag)

    @property
    def repo(self):
        return Repo(self.repo_abs_path)

    @property
    def repo_abs_path(self):
        return str(settings.REPO_BASE / self.repo_rel_path)

    @property
    def repo_rel_path(self):
        """Return filesystem path of repository"""
        return Path(str(self.author.id)) / (self.entity_type + 's') / self.name

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Model entities'


class EntityManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(entity_type=self.model.entity_type)

    def create(self, **kwargs):
        kwargs['entity_type'] = self.model.entity_type
        return super().create(**kwargs)


class ModelEntity(Entity):
    entity_type = Entity.ENTITY_TYPE_MODEL

    objects = EntityManager()

    class Meta:
        proxy = True


class ProtocolEntity(Entity):
    entity_type = Entity.ENTITY_TYPE_PROTOCOL

    objects = EntityManager()

    class Meta:
        proxy = True


class EntityUpload(models.Model):
    entity = models.ForeignKey(ModelEntity)
    upload = models.FileField(upload_to='uploads')
    original_name = models.CharField(max_length=255)
