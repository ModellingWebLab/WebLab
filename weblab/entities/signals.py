
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
    instance.repo.delete()
