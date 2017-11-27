from django.apps import AppConfig
from django.db.models.signals import post_save

from .signals import entity_created


class EntitiesConfig(AppConfig):
    name = 'entities'

    def ready(self):
        from .models import ModelEntity, ProtocolEntity
        post_save.connect(entity_created, sender=ModelEntity)
        post_save.connect(entity_created, sender=ProtocolEntity)
