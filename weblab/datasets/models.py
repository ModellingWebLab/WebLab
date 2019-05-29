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
    model = models.ForeignKey(ModelEntity, related_name='model_experimental_dataset')
    protocol = models.ForeignKey(ProtocolEntity, related_name='protocol_experimental_dataset')

    # Note that we can't use a ForeignKey here, because versions of models and protocols
    # are not stored in the DB - they are just commits in the associated git repo.
    # So instead we store the full git SHA as a string.
    model_version = models.CharField(max_length=50)
    protocol_version = models.CharField(max_length=50)

    class Meta:
        unique_together = ('model', 'protocol', 'model_version', 'protocol_version')
        verbose_name_plural = 'ExperimentalDatasets'

        permissions = (
            ('create_dataset_experiment', 'Can create dataset experiments'),
        )

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.get_name()

    def get_name(self, model_version=False, proto_version=False):
        """
        Get experiment name, optionally including model and/or protocol versions

        :param model_version: Whether to include model version
        :param proto_version: Whether to include protocol version
        """
        return '{0} / {1}'.format(
            ('{0}@{1}' if model_version else '{0}').format(
                self.model.name, self.nice_model_version),
            ('{0}@{1}' if proto_version else '{0}').format(
                self.protocol.name, self.nice_protocol_version),
        )

    @property
    def visibility(self):
        return get_joint_visibility(
            self.model.get_version_visibility(
                self.model_version,
                default=self.model.DEFAULT_VISIBILITY),
            self.protocol.get_version_visibility(
                self.protocol_version,
                default=self.protocol.DEFAULT_VISIBILITY),
        )

    @property
    def viewers(self):
        """
        Get users which have special permissions to view this experiment

        We do not handle the case where both model and protocol are public,
        since this would make the experiment also public and therefore
        visible to every user - so calling this method makes very little sense.

        :return: `set` of `User` objects
        """
        if self.protocol.visibility == Visibility.PUBLIC:
            return self.model.viewers
        elif self.model.visibility == Visibility.PUBLIC:
            return self.protocol.viewers
        else:
            return self.model.viewers & self.protocol.viewers

    def is_visible_to_user(self, user):
        """
        Can the user view the experiment?

        :param user: user to test against

        :returns: True if the user is allowed to view the experiment, False otherwise
        """
        return visibility_check(self.visibility, self.viewers, user)

    @property
    def latest_version(self):
        return self.versions.latest('created_at')

    @property
    def nice_model_version(self):
        """Use tags to give a nicer representation of the commit id"""
        return self.model.nice_version(self.model_version)

    @property
    def nice_protocol_version(self):
        """Use tags to give a nicer representation of the commit id"""
        return self.protocol.nice_version(self.protocol_version)

    @property
    def latest_result(self):
        try:
            return self.latest_version.status
        except ExperimentalDataset.DoesNotExist:
            return ''


class RunningDatasetExperiment(models.Model):
    """
    A current run of an ExperimentVersion
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    task_id = models.CharField(max_length=50)


class DatasetFile(models.Model):
    entity = models.ForeignKey(ExperimentalDataset, related_name='files')
    upload = models.FileField(upload_to='uploads')
    original_name = models.CharField(max_length=255)

    def __str__(self):
        return self.original_name


