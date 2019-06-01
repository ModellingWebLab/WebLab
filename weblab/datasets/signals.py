from shutil import rmtree


def dataset_created(sender, instance, created, **kwargs):
    """
    Signal callback when a dataset has been created.
    """
    if created:
        instance.abs_path.mkdir(exist_ok=True, parents=True)


def dataset_deleted(sender, instance, **kwargs):
    """
    Signal callback when a dataset is about to be deleted.
    """
    if instance.abs_path.is_dir():
        rmtree(str(instance.abs_path))
