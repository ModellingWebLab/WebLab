from django.apps import AppConfig
from django.db.models.signals import post_delete


class StoriesConfig(AppConfig):
    name = 'stories'

    def ready(self):
        """
        Executed when stories app has bee loaded.
        """
        from entities.models import ModelEntity, ModelGroup
        from .models import StoryGraph

        def model_deleted(sender, instance, **kwargs):
            """
            Signal callback when an entity is about to be deleted.
            This signal specificaly deals with cases where model groups ans tory graphs
            are left hanging after user deletion.
            """
            # delete story graphs without cached model versions
            StoryGraph.objects.filter(cachedmodelversions=None).delete()
            # delete model groups without models
            ModelGroup.objects.filter(models=None).delete()

        # Connect signal to post_save
        post_delete.connect(model_deleted, ModelEntity)

