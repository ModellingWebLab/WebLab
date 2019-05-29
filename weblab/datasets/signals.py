
def dataset_created(sender, instance, created, **kwargs):
    """
    Signal callback when an dataset has been created.
    """
    if created:
        instance.repo.create()


def dataset_deleted(sender, instance, **kwargs):
    """
    Signal callback when an dataset is about to be deleted.
    """
    instance.repo.delete()
