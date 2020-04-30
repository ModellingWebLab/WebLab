from django.apps import AppConfig
from django.db.models.signals import pre_delete

from .signals import runnable_deleted, running_experiment_deleted


class ExperimentsConfig(AppConfig):
    name = 'experiments'

    def ready(self):
        from .models import Runnable, RunningExperiment

        pre_delete.connect(runnable_deleted, Runnable)
        pre_delete.connect(running_experiment_deleted, RunningExperiment)
