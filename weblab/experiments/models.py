from pathlib import Path

from django.conf import settings
from django.db import models

from core import visibility
from core.combine import ZippedArchiveReader
from entities.models import ModelEntity, ProtocolEntity


class Experiment(models.Model):
    creation_date = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL)
    visibility = models.CharField(
        max_length=16,
        choices=visibility.CHOICES,
        help_text=visibility.HELP_TEXT.replace('\n', '<br />'),
    )

    model = models.ForeignKey(ModelEntity, related_name='model_experiments')
    protocol = models.ForeignKey(ProtocolEntity, related_name='protocol_experiments')

    class Meta:
        unique_together = ('model', 'protocol')
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


class ExperimentVersion(models.Model):
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
    author = models.ForeignKey(settings.AUTH_USER_MODEL)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    return_text = models.TextField(blank=True)
    task_id = models.CharField(max_length=50, blank=True)
    model_version = models.CharField(max_length=50)
    protocol_version = models.CharField(max_length=50)

    def __str__(self):
        return '%s at %s: (%s)' % (self.experiment, self.created_at, self.status)

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
            return ZippedArchiveReader(str(self.archive_path)).files
        else:
            return []

    def open_file(self, name):
        return ZippedArchiveReader(str(self.archive_path)).open_file(name)
