from django.apps import AppConfig
from django.db.models.signals import post_save, pre_delete

#from .signals import entity_created, entity_deleted


class DatasetsConfig(AppConfig):
    name = 'datasets'

    def ready(self):
        from .models import ExperimentalDataset

