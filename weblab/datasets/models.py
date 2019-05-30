import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from core.combine import ArchiveReader
from core.models import UserCreatedModelMixin
from core.visibility import get_joint_visibility, Visibility, visibility_check
from core.models import VisibilityModelMixin
from entities.models import ModelEntity, ProtocolEntity

class ExperimentalDataset(UserCreatedModelMixin, VisibilityModelMixin, models.Model):
    """Prototyping class for experimental datasets
    """
    protocol = models.ForeignKey(ProtocolEntity, related_name='protocol_experimental_datasets')

    class Meta:
        verbose_name_plural = 'ExperimentalDatasets'

        permissions = (
            ('create_dataset', 'Can create experiment datasets'),
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


