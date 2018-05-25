from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_experiment_finished_email(experiment_version):
    author = experiment_version.author

    if author.receive_emails:
        body = render_to_string(
            'emails/experiment_finished.txt',
            {
                'user': author,
                'experiment_version': experiment_version,
                'base_url': settings.BASE_URL,
            }
        )

        send_mail(
            'Web Lab experiment finished',
            body,
            settings.SERVER_EMAIL,
            [author.email],
        )
