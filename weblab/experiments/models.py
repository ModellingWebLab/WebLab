import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from core.models import FileCollectionMixin, UserCreatedModelMixin
from core.visibility import Visibility, get_joint_visibility, visibility_check
from entities.models import ModelEntity, ProtocolEntity
from repocache.models import CachedModelVersion, CachedProtocolVersion


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

    model_version = models.ForeignKey(CachedModelVersion, default=None, null=False, related_name='model_ver_exps')
    protocol_version = models.ForeignKey(CachedProtocolVersion, default=None, null=False, related_name='pro_ver_exps')

    class Meta:
        unique_together = ('model', 'protocol', 'model_version', 'protocol_version')
        verbose_name_plural = 'Experiments'

        permissions = (
            ('create_experiment', 'Can create experiments'),
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
        model_part = self.model.name
        if model_version:
            model_part += '@' + self.model_version.nice_version()
        proto_part = self.protocol.name
        if proto_version:
            proto_part += '@' + self.protocol_version.nice_version()
        return '{0} / {1}'.format(model_part, proto_part)

    @property
    def visibility(self):
        return get_joint_visibility(self.model_version.visibility, self.protocol_version.visibility)

    @property
    def viewers(self):
        """
        Get users which have special permissions to view this experiment

        We do not handle the case where both model and protocol are public,
        since this would make the experiment also public and therefore
        visible to every user - so calling this method makes very little sense.

        :return: `set` of `User` objects
        """
        if self.protocol.visibility != Visibility.PRIVATE:
            return self.model.viewers
        elif self.model.visibility != Visibility.PRIVATE:
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
        return self.model_version.nice_version()

    @property
    def nice_protocol_version(self):
        """Use tags to give a nicer representation of the commit id"""
        return self.protocol_version.nice_version()

    @property
    def latest_result(self):
        try:
            return self.latest_version.status
        except Runnable.DoesNotExist:
            return ''


class Runnable(UserCreatedModelMixin, FileCollectionMixin, models.Model):
    """ Runnable base class
    Represents experiments and fitting specs that have the facility to
    run on the back-end,
    The current status of the run is recorded as well as the and results when completed.
    """
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

    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    return_text = models.TextField(blank=True)

    def __str__(self):
        return '%s at %s: (%s)' % (self.experiment, self.created_at, self.status)

    class Meta:
        indexes = [
            models.Index(fields=['created_at'])
        ]

    @property
    def name(self):
        return '{:%Y-%m-%d %H:%M:%S}'.format(self.created_at)

    @property
    def run_number(self):
        return self.experiment.versions.filter(created_at__lte=self.created_at).count()

    @property
    def is_latest(self):
        return not self.experiment.versions.filter(created_at__gt=self.created_at).exists()

    @property
    def visibility(self):
        return self.experiment.visibility

    @property
    def viewers(self):
        return self.experiment.viewers

    @property
    def abs_path(self):
        return Path(settings.EXPERIMENT_BASE, str(self.id))

    @property
    def archive_name(self):
        return 'results.omex'

    @property
    def signature(self):
        return str(self.running.first().id)

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


class ExperimentVersion(Runnable):
    """ ExperimentVersion class
    This records a single run of a particular Experiment.
    The same model/protocol combination may be run more than once,
    resulting in an Experiment having multiple versions.
    """
    experiment = models.ForeignKey(Experiment, related_name='versions')

    @property
    def parent(self):
        """The Experiment this is a version of."""
        return self.experiment


class RunningExperiment(models.Model):
    """ Class to track an in-progress Runnable instance.
    It adds functionality to link to the task id on the back-end system, so that returned results
    can be linked to the appropriate Runnable.
    The running tasks can be cancelled by deleting using the front-end.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    runnable = models.ForeignKey(Runnable, related_name='running')

    task_id = models.CharField(max_length=50)


class PlannedExperiment(models.Model):
    """Specification for an experiment that should be run.

    This is provided as part of the JSON data when displaying entity versions, so that JS code
    can submit new experiment runs automatically and notify the user of success/failure. See
    https://github.com/ModellingWebLab/WebLab/pull/114, https://github.com/ModellingWebLab/WebLab/issues/244.
    """
    submitter = models.ForeignKey(settings.AUTH_USER_MODEL,
                                  help_text='the user that requested this experiment',
                                  null=True,  # To support migrating; new instances should provide this!
                                  default=None,
                                  )

    model = models.ForeignKey(ModelEntity, related_name='planned_model_experiments')
    protocol = models.ForeignKey(ProtocolEntity, related_name='planned_protocol_experiments')

    model_version = models.CharField(max_length=50)
    protocol_version = models.CharField(max_length=50)

    class Meta:
        indexes = [
            models.Index(fields=['submitter'])
        ]
        unique_together = ('model', 'protocol', 'model_version', 'protocol_version')
