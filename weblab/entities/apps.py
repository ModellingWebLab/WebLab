from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save, pre_delete

from .signals import entity_created, entity_deleted, entity_post_deleted


class EntitiesConfig(AppConfig):
    name = 'entities'

    def ready(self):
        from .models import Entity, ModelEntity, ProtocolEntity

        # Messages might come from the base Entity class or the proxy subclasses
        # depending on how the views are set up / where the action is invoked.
        # This covers all bases for creation and deletion.
        for sender in [Entity, ModelEntity, ProtocolEntity]:
            post_save.connect(entity_created, sender)
            pre_delete.connect(entity_deleted, sender)
            post_delete.connect(entity_post_deleted, sender)
