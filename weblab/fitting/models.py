from django.db import models

from core.models import UserCreatedModelMixin
from core.visibility import get_joint_visibility
from datasets.models import Dataset
from entities.models import (
    Entity,
    EntityManager,
    ModelEntity,
    ProtocolEntity,
)
from experiments.models import ExperimentMixin, Runnable
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


class FittingResult(ExperimentMixin, UserCreatedModelMixin, models.Model):
    """Represents the result of running a parameter fitting experiment.

    This class essentially just stores the links to (particular versions of) a fitting spec,
    model, protocol, and dataset. The actual results are contained within FittingResultVersion
    instances, available as .versions, that represent specific runs of the fitting experiment.

    There will only ever be one FittingResult for a given combination of model, protocol,
    dataset and fitting spec versions.

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
    def entities(self):
        return (self.fittingspec, self.dataset, self.model, self.protocol)


class FittingResultVersion(Runnable):
    """The results of a single parameter fitting run."""
    fittingresult = models.ForeignKey(FittingResult, related_name='versions')

    @property
    def parent(self):
        """The FittingResult this is a version of."""
        return self.fittingresult
