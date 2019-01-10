from django.apps import AppConfig
from django.db.models.signals import pre_delete

from .signals import experiment_version_deleted


class ExperimentsConfig(AppConfig):
    name = 'experiments'

    def ready(self):
        from .models import ExperimentVersion

        pre_delete.connect(experiment_version_deleted, ExperimentVersion)
