
def entity_created(sender, instance, created, **kwargs):
    """
    Signal callback when an entity has been created.
    """
    if created:
        instance.repo.create()


def entity_deleted(sender, instance, **kwargs):
    """
    Signal callback when an entity is about to be deleted.
    """
    if instance.repo_abs_path.exists():
        instance.repo.delete()

    from stories.models import StoryGraph
    from .models import ModelGroup

    # delete story graphs without cached model versions
    StoryGraph.objects.filter(cachedmodelversions=None).delete()
    # delete model groups without models
    ModelGroup.objects.filter(models=None).delete()
