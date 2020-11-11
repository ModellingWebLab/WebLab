from shutil import rmtree

from .emails import send_user_creation_email


def user_created(sender, instance, created, **kwargs):
    if created:
        send_user_creation_email(instance)


def user_deleted(sender, instance, **kwargs):
    for kind in instance.STORAGE_DIRS:
        path = instance.get_storage_dir(kind)
        if path.is_dir():
            rmtree(str(path))
