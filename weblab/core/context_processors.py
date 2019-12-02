from django.contrib import messages

from . import visibility


def common(request):
    info_messages = []
    error_messages = []
    for message in messages.get_messages(request):
        if message.level == messages.ERROR:
            error_messages.append(message)
        elif message.level == messages.INFO:
            info_messages.append(message)

    return {
        'VISIBILITY_HELP': visibility.HELP_TEXT,
        'ERROR_MESSAGES': error_messages,
        'INFO_MESSAGES': info_messages,
        'current_namespace': request.resolver_match.namespace,
    }
