from shutil import rmtree


def experiment_version_deleted(sender, instance, **kwargs):
    """
    Signal callback when an experiment version is about to be deleted.

    Ensure the experiment data directory is also deleted.

    If the directory doesn't exist yet (because no results received) this is a no-op.
    """
    if instance.abs_path.is_dir():
        rmtree(str(instance.abs_path))
