from . import visibility


def common(request):
    return {
        'VISIBILITY_HELP': visibility.HELP_TEXT
    }
