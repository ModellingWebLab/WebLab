from pathlib import Path

from django.conf import settings
from django.db import models

from core.combine import ArchiveReader
from core.models import UserCreatedModelMixin, VisibilityModelMixin
from entities.models import ModelEntity, ProtocolEntity


class Experiment(UserCreatedModelMixin, models.Model):
    """A specific version of a protocol run on a specific version of a model

    This class essentially just stores the model & protocol links. The results are
    contained within ExperimentVersion instances, available as .versions, that
    represent specific runs of the experiment.

    There will only ever be one Experiment for a given combination of model version
    and protocol version.
    """
    model = models.ForeignKey(ModelEntity, related_name='model_experiments')
    protocol = models.ForeignKey(ProtocolEntity, related_name='protocol_experiments')

    # Note that we can't use a ForeignKey here, because versions of models and protocols
    # are not stored in the DB - they are just commits in the associated git repo.
    model_version = models.CharField(max_length=50)     # The full git commit SHA
    protocol_version = models.CharField(max_length=50)  # The full git commit SHA

    class Meta:
        unique_together = ('model', 'protocol', 'model_version', 'protocol_version')
        verbose_name_plural = 'Experiments'

        permissions = (
            ('create_experiment', 'Can create experiments'),
            ('force_new_experiment_version', 'Can force new experiment version'),
        )

    def __str__(self):
        return self.name

    @property
    def name(self):
        return '%s / %s' % (self.model.name, self.protocol.name)

    @property
    def latest_version(self):
        return self.versions.latest('created_at')

    @property
    def latest_result(self):
        try:
            return self.latest_version.status
        except ExperimentVersion.DoesNotExist:
            return ''


class ExperimentVersion(UserCreatedModelMixin, VisibilityModelMixin, models.Model):
    STATUS_QUEUED = "QUEUED"
    STATUS_RUNNING = "RUNNING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_PARTIAL = "PARTIAL"
    STATUS_FAILED = "FAILED"
    STATUS_INAPPLICABLE = "INAPPLICABLE"

    STATUS_CHOICES = (
        (STATUS_QUEUED, STATUS_QUEUED),
        (STATUS_RUNNING, STATUS_RUNNING),
        (STATUS_SUCCESS, STATUS_SUCCESS),
        (STATUS_PARTIAL, STATUS_PARTIAL),
        (STATUS_FAILED, STATUS_FAILED),
        (STATUS_INAPPLICABLE, STATUS_INAPPLICABLE),
    )

    experiment = models.ForeignKey(Experiment, related_name='versions')
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    return_text = models.TextField(blank=True)
    task_id = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return '%s at %s: (%s)' % (self.experiment, self.created_at, self.status)

    @property
    def name(self):
        model_repo = self.experiment.model.repo
        protocol_repo = self.experiment.protocol.repo
        return '%s / %s' % (model_repo.get_name_for_commit(self.experiment.model_version),
                            protocol_repo.get_name_for_commit(self.experiment.protocol_version))

    @property
    def abs_path(self):
        return Path(settings.EXPERIMENT_BASE, str(self.id))

    @property
    def archive_path(self):
        return self.abs_path / 'results.omex'

    @property
    def signature(self):
        return str(self.id)

    @property
    def is_running(self):
        return self.status == self.STATUS_RUNNING

    @property
    def is_finished(self):
        return self.status in (
            self.STATUS_SUCCESS,
            self.STATUS_PARTIAL,
            self.STATUS_FAILED,
        )

    def update(self, status, txt):
        """
        Update the results / status of the experiment
        """
        self.status = status
        self.return_text = txt
        self.save()

    @property
    def files(self):
        if self.archive_path.exists():
            return ArchiveReader(str(self.archive_path)).files
        else:
            return []

    def open_file(self, name):
        return ArchiveReader(str(self.archive_path)).open_file(name)
