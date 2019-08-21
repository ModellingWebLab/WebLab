from django.apps import AppConfig
from django.db.models.signals import post_save, pre_delete

from .signals import dataset_created, dataset_deleted


class DatasetsConfig(AppConfig):
    name = 'datasets'

    def ready(self):
        from .models import Dataset
        post_save.connect(dataset_created, Dataset)
        pre_delete.connect(dataset_deleted, Dataset)
