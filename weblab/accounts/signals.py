from shutil import rmtree

from .emails import send_user_creation_email


def user_created(sender, instance, created, **kwargs):
    if created:
        send_user_creation_email(instance)


def user_deleted(sender, instance, created, **kwargs):
    if instance.get_storage_dir('repo').is_dir():
        rmtree(str(instance.get_storage_dir('repo')))

    if instance.get_storage_dir('dataset').is_dir():
        rmtree(str(instance.get_storage_dir('dataset')))
