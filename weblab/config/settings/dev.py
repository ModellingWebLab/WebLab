import copy
import sys

from .base import *  # noqa


DEBUG = True
LOG_DEBUG = DEBUG

ALLOWED_HOSTS = ['*']

# Log all emails to console
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Don't make life difficult for ourselves with password restrictions on dev
AUTH_PASSWORD_VALIDATORS = []

# Rollbar server reporting
ROLLBAR = {
    'access_token': secrets.ROLLBAR_POST_SERVER_ITEM_ACCESS_TOKEN,  # noqa
    'environment': 'development' if DEBUG else 'production',
    'branch': 'master',
    'root': str(BASE_DIR),  # noqa
}

# Logging settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'verbose',
        },
        'console_err': {
            'level': 'WARNING',
            'class': 'logging.StreamHandler',
            'stream': sys.stderr,
            'formatter': 'verbose',
        },
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(name)s: %(message)s',
        },
        'simple': {
            'format': '%(levelname)s %(message)s',
        },
    },
    'loggers': {
        # Root logger
        '': {
            'handlers': ['console'],
            'disabled': False,
            'level': 'DEBUG' if LOG_DEBUG else 'INFO',
        },
        'django': {
            'handlers': ['console'],
            'level': 'DEBUG' if LOG_DEBUG else 'INFO',
            'propagate': False,
        },
    }
}

local_logger_conf = {
    'handlers': ['console'],
    'level': 'DEBUG' if LOG_DEBUG else 'INFO',
}
LOGGING['loggers'].update({
    app.split('.')[0]: copy.deepcopy(local_logger_conf)
    for app in LOCAL_APPS
})
