from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_user_creation_email(user):
    """
    Email all admin users when a new user is created
    """

    # Don't email the created user about it
    admin_emails = list(
        get_user_model().objects.admins().exclude(pk=user.pk).values_list('email', flat=True))
    body = render_to_string(
        'emails/user_created.txt',
        {
            'user': user,
            'base_url': settings.BASE_URL,
        }
    )

    send_mail(
        'New WebLab user created',
        body,
        settings.SERVER_EMAIL,
        admin_emails,
    )
