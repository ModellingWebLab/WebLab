from shutil import rmtree


def experiment_version_deleted(sender, instance, **kwargs):
    """
    Signal callback when an experiment version is about to be deleted.

    Ensure the experiment data directory is also deleted.
    """
    rmtree(str(instance.abs_path))
