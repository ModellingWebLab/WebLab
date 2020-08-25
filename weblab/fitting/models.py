from django.db import models

from core.models import UserCreatedModelMixin
from core.visibility import Visibility, get_joint_visibility, visibility_check
from datasets.models import Dataset
from entities.models import (
    Entity,
    EntityManager,
    ModelEntity,
    ProtocolEntity,
)
from experiments.models import Runnable
from repocache.models import CachedFittingSpecVersion, CachedModelVersion, CachedProtocolVersion


class FittingSpec(Entity):
    """
    Represents parameter fitting specifications.
    These are versioned entities, backed by a git repository.

    It links to a ProtocolEntity (not a specific version thereof) representing
    the experimental scenario which can be used to fit models.

    Running a fitting specification with (specific versions of) a ModelEntity,
    ProtocolEntity and Dataset will result in a FittingResult being generated.
    """
    entity_type = Entity.ENTITY_TYPE_FITTINGSPEC
    other_type = Entity.ENTITY_TYPE_MODEL
    is_fitting_spec = True

    protocol = models.ForeignKey(
        ProtocolEntity, related_name='fitting_specs',
        help_text='the experimental scenario used to fit models',
    )

    objects = EntityManager()

    class Meta:
        verbose_name = 'fitting specification'

    # We change the default display & URL form for this entity type, since the default looks bad!
    display_type = Meta.verbose_name
    url_type = 'spec'

    # The 'edit_entity' object-level permission is only in the entities app,
    # so we need to delegate via our parent link when accessing it.

    def is_editable_by(self, user):
        return self.entity_ptr.is_editable_by(user)

    def add_collaborator(self, user):
        return self.entity_ptr.add_collaborator(user)

    def remove_collaborator(self, user):
        return self.entity_ptr.remove_collaborator(user)

    @property
    def collaborators(self):
        return self.entity_ptr.collaborators


class FittingResult(UserCreatedModelMixin, models.Model):
    """Represents the result of running a parameter fitting experiment.

    This class essentially just stores the links to (particular versions of) a fitting spec,
    model, protocol, and dataset. The actual results are contained within FittingResultVersion
    instances, available as .versions, that represent specific runs of the fitting experiment.

    There will only ever be one FittingResult for a given combination of model, protocol,
    dataset and fitting spec versions.

    TODO: Consider creating a mixin for fields/methods shared with Experiment.
    """
    fittingspec = models.ForeignKey(FittingSpec, related_name='fitting_results')
    dataset = models.ForeignKey(Dataset, related_name='fitting_results')
    model = models.ForeignKey(ModelEntity, related_name='model_fitting_results')
    protocol = models.ForeignKey(ProtocolEntity, related_name='protocol_fitting_results')

    model_version = models.ForeignKey(CachedModelVersion, default=None, null=False, related_name='model_ver_fitres')
    protocol_version = models.ForeignKey(CachedProtocolVersion, default=None, null=False, related_name='pro_ver_fitres')
    fittingspec_version = models.ForeignKey(
        CachedFittingSpecVersion,
        default=None, null=False, related_name='fit_ver_fitres',
    )

    class Meta:
        unique_together = ('fittingspec', 'dataset', 'model', 'protocol',
                           'fittingspec_version', 'model_version', 'protocol_version')

        permissions = (
            ('run_fits', 'Can run parameter fitting experiments'),
        )

    def __str__(self):
        return self.name

    @property
    def name(self):
        """There isn't an obvious easy naming for fitting results..."""
        return 'Fit {} to {} using {}'.format(self.model.name, self.dataset.name, self.fittingspec.name)

    @property
    def visibility(self):
        return get_joint_visibility(
            self.fittingspec_version.visibility,
            self.dataset.visibility,
            self.model_version.visibility,
            self.protocol_version.visibility,
        )

    @property
    def viewers(self):
        """
        Get users which have special permissions to view this experiment.

        We take the intersection of users with special permissions to view each object
        (model, fitting spec, etc) involved, if that object is private. If it's public,
        we can ignore it because everyone can see it.

        :return: `set` of `User` objects
        """
        relevant_viewers = []
        for obj in (self.fittingspec, self.dataset, self.model, self.protocol):
            if obj.visibility == Visibility.PRIVATE:
                relevant_viewers.append(obj.viewers)
        return set.intersection(*relevant_viewers)

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


class FittingResultVersion(Runnable):
    """The results of a single parameter fitting run."""
    fittingresult = models.ForeignKey(FittingResult, related_name='versions')

    @property
    def parent(self):
        """The FittingResult this is a version of."""
        return self.fittingresult
