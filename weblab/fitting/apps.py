from django.apps import AppConfig
from django.db.models.signals import post_save, pre_delete

from entities.signals import entity_created, entity_deleted


class FittingConfig(AppConfig):
    name = 'fitting'

    def ready(self):
        from .models import FittingSpec

        # Messages might come from the base Entity class or our new subclass
        # depending on how the views are set up / where the action is invoked.
        # This covers all bases for creation and deletion.
        post_save.connect(entity_created, FittingSpec)
        pre_delete.connect(entity_deleted, FittingSpec)
