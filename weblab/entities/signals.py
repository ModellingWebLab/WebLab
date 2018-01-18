
def entity_created(sender, instance, created, **kwargs):
    """
    Signal callback when an entity has been created.
    """
    if created:
        instance.init_repo()


def entity_deleted(sender, instance, **kwargs):
    """
    Signal callback when an entity is about to be deleted.
    """
    instance.delete_repo()
