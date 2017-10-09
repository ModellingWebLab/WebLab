from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator
from django.db import models


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

    repository_url = models.URLField()

    @property
    def full_repository_url(self):
        return str(settings.REPO_BASE / entity.repository_url)

    @classmethod
    def get_repo_path(cls, user_id, repo_name):
        """Return filesystem path of repository"""
        return Path(str(user_id)) / cls.REPO_DIRECTORY / repo_name

    def __str__(self):
        return self.name

    class Meta:
        abstract = True


class ModelEntity(Entity):
    REPO_DIRECTORY = 'models'

    class Meta:
        verbose_name_plural = 'Model entities'


class ProtocolEntity(Entity):
    REPO_DIRECTORY = 'protocols'

    class Meta:
        verbose_name_plural = 'Protocol entities'

class EntityUpload(models.Model):
    upload = models.FileField(upload_to='uploads')
