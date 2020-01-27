from .base import *  # noqa


# Settings file used by pytest, whether locally or on Travis
class InvalidStringShowWarning(str):
    def __mod__(self, other):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("In template, undefined variable or unknown value for: '%s'" % (other,))
        return ""


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'string_if_invalid': InvalidStringShowWarning("%s"),
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
                'core.context_processors.common',
            ],
        },
    },
]
