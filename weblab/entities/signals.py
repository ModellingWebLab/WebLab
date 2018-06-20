
def entity_created(sender, instance, created, **kwargs):
    """
    Signal callback when an entity has been created.
    """
    if created:
        if instance.git_remote_url:
            instance.repo.clone_from(instance.git_remote_url)
        else:
            instance.repo.create()


def entity_deleted(sender, instance, **kwargs):
    """
    Signal callback when an entity is about to be deleted.
    """
    instance.repo.delete()
