from django.apps import AppConfig
from django.db.models.signals import post_save, pre_delete

#from .signals import entity_created, entity_deleted

# not yet used by may be needed when we have signals working


class DatasetsConfig(AppConfig):
    name = 'datasets'

    def ready(self):
        return
#        from .models import ExperimentalDataset

