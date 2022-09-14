from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from stories.models import Story


def send_story_changed_email(graphs):
    stories = Story.objects.filter(id__in=graphs.filter(email_sent=False).
                                   values_list('story_id', flat=True)).filter(email_sent=False)
    for story in stories:
        author = story.author

        if author.receive_story_emails:
            print('sending email')
            body = render_to_string(
                'emails/story_versions_changed.txt',
                {
                    'user': author,
                    'story': story,
                    'base_url': settings.BASE_URL,
                }
            )

            send_mail(
                'Your weblab story is affected by model or protocol changes',
                body,
                settings.SERVER_EMAIL,
                [author.email],
            )

            story.email_sent = True
            story.save()

    # prevent re-sending emails
    for graph in graphs:
        graph.email_sent = True
        graph.save()
