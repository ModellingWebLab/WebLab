from django.db import models

from entities.models import Entity, EntityManager, ProtocolEntity


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
