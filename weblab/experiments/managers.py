from django.db import models

from core.visibility import visible_entity_ids
from entities.models import ModelEntity, ProtocolEntity


class ExperimentVersionManager(models.Manager):
    def visible_to(self, user):
        """
        Get a queryset of experiments visible to the given user
        """
        visible_ids = visible_entity_ids(user)
        visible_models = ModelEntity.objects.filter(pk__in=visible_ids)
        visible_protocols = ProtocolEntity.objects.filter(pk__in=visible_ids)
        return self.get_queryset().filter(
            experiment__model__in=visible_models,
            experiment__protocol__in=visible_protocols,
        )
