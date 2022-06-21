import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from core.models import FileCollectionMixin, UserCreatedModelMixin
from core.visibility import Visibility, get_joint_visibility, visibility_check
from entities.models import ModelEntity, ProtocolEntity
from repocache.models import CachedModelVersion, CachedProtocolVersion


class ExperimentMixin(models.Model):
    """
    Model mixin for different types of experiment

    Models must have model, model_version, protocol and protocol_version fields
    and be the parent of a Runnable-derived model.
    """
    def __str__(self):
        return self.name

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

    @property
    def entities(self):
        """Entity objects related to this experiment"""
        return (self.model, self.protocol)

    def is_visible_to_user(self, user):
        """
        Can the user view the experiment?

        :param user: user to test against

        :returns: True if the user is allowed to view the experiment, False otherwise
        """
        return visibility_check(self.visibility, self.viewers, user)

    @property
    def viewers(self):
        """
        Get users which have special permissions to view this experiment.

        We take the intersection of users with special permissions to view each object
        (model, fitting spec, etc) involved, if that object is private. If it's public,
        we can ignore it because everyone can see it.

        :return: `set` of `User` objects
        """
        viewers = [
            obj.viewers
            for obj in self.entities
            if obj.visibility == Visibility.PRIVATE
        ]
        return set.intersection(*viewers) if viewers else {}

    class Meta:
        abstract = True


class Experiment(ExperimentMixin, UserCreatedModelMixin, models.Model):
    """A specific version of a protocol run on a specific version of a model

    This class essentially just stores the model & protocol links. The results are
    contained within ExperimentVersion instances, available as .versions, that
    represent specific runs of the experiment.

    There will only ever be one Experiment for a given combination of model version
    and protocol version.
    """
    model = models.ForeignKey(ModelEntity, related_name='model_experiments', on_delete=models.CASCADE)
    protocol = models.ForeignKey(ProtocolEntity, related_name='protocol_experiments', on_delete=models.CASCADE)

    model_version = models.ForeignKey(CachedModelVersion, default=None, null=False,
                                      related_name='model_ver_exps', on_delete=models.CASCADE)
    protocol_version = models.ForeignKey(CachedProtocolVersion,
                                         default=None, null=False,
                                         related_name='pro_ver_exps', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('model', 'protocol', 'model_version', 'protocol_version')
        verbose_name_plural = 'Experiments'

        indexes = [
            models.Index(fields=['model_version', 'protocol_version']),
        ]

        permissions = (
            ('create_experiment', 'Can create experiments'),
        )

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

    class Meta:
        indexes = [
            models.Index(fields=['created_at'])
        ]

    def __str__(self):
        return '%s at %s: (%s)' % (self.parent, self.created_at, self.status)

    @property
    def parent(self):
        """E.g. the Experiment this is a version of. Must be defined by subclasses."""
        raise NotImplementedError

    @property
    def name(self):
        return '{:%Y-%m-%d %H:%M:%S}'.format(self.created_at)

    @property
    def run_number(self):
        return self.parent.versions.filter(created_at__lte=self.created_at).count()

    @property
    def is_latest(self):
        return not self.parent.versions.filter(created_at__gt=self.created_at).exists()

    @property
    def visibility(self):
        return self.parent.visibility

    @property
    def viewers(self):
        return self.parent.viewers

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
    experiment = models.ForeignKey(Experiment, related_name='versions', on_delete=models.CASCADE)

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

    runnable = models.ForeignKey(Runnable, related_name='running', on_delete=models.CASCADE)

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
                                  on_delete=models.CASCADE,
                                  )

    model = models.ForeignKey(ModelEntity, related_name='planned_model_experiments', on_delete=models.CASCADE)
    protocol = models.ForeignKey(ProtocolEntity, related_name='planned_protocol_experiments', on_delete=models.CASCADE)

    model_version = models.CharField(max_length=50)
    protocol_version = models.CharField(max_length=50)

    class Meta:
        indexes = [
            models.Index(fields=['submitter'])
        ]
        unique_together = ('model', 'protocol', 'model_version', 'protocol_version')
