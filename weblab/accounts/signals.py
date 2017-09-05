from .emails import send_user_creation_email


def user_created(sender, instance, created, **kwargs):
    if created:
        send_user_creation_email(instance)
