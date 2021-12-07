rom django.apps import AppConfig
from django.db.models.signals import post_delete


class StoriesConfig(AppConfig):
    name = 'stories'

    def ready(self):
    """
    Executed when stories app has bee loaded.
    """
        from .models import ModelEntity
        from entities.models import ModelGroup
        def model_deleted(sender, instance, **kwargs):
        """
        Signal callback when an entity is about to be deleted.
        """
            # delete story graphs without cached model versions
            StoryGraph.objects.filter(cachedmodelversions=None).delete()
            # delete model groups without models
            ModelGroup.objects.filter(models=None).delete()

        # When a model gets deleted but is in use in stories (e.g. because the user account is deleted) weneed to act accordingly
        post_delete.connect(model_deleted, ModelEntity)

