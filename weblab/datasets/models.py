import uuid
from pathlib import Path

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models

from core.combine import ArchiveReader
from core.models import UserCreatedModelMixin
from core.visibility import get_joint_visibility, Visibility, visibility_check
from core.models import VisibilityModelMixin
from entities.models import ModelEntity, ProtocolEntity


class ExperimentalDataset(UserCreatedModelMixin, VisibilityModelMixin, models.Model):
    """Prototyping class for experimental datasets
    """
    name = models.CharField(validators=[MinLengthValidator(2)], max_length=255)

    protocol = models.ForeignKey(ProtocolEntity, related_name='protocol_experimental_datasets')

    class Meta:
        ordering = ['name']
        unique_together = ('name', 'author')
        verbose_name_plural = 'ExperimentalDatasets'

        permissions = (
            ('create_dataset', 'Can create experimental datasets'),
        )

    def __str__(self):
        return self.name

    def is_visible_to_user(self, user):
        """
        Can the user view the dataset?

        :param user: user to test against

        :returns: True if the user is allowed to view the dataset, False otherwise
        """
        return visibility_check(self.visibility, self.viewers, user)


class DatasetFile(models.Model):
    dataset = models.ForeignKey(ExperimentalDataset, related_name='files')
    upload = models.FileField(upload_to='uploads')
    original_name = models.CharField(max_length=255)

    def __str__(self):
        return self.original_name



