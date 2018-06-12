from django.db import models

from core.visibility import visibility_query
from entities.models import ModelEntity, ProtocolEntity


class ExperimentVersionManager(models.Manager):
    def visible_to(self, user):
        """
        Get a queryset of experiments visible to the given user
        """
        vis_query = visibility_query(user)
        visible_models = ModelEntity.objects.filter(vis_query)
        visible_protocols = ProtocolEntity.objects.filter(vis_query)
        return self.get_queryset().filter(
            experiment__model__in=visible_models,
            experiment__protocol__in=visible_protocols,
        )
