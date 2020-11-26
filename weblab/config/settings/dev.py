# Ignore warnings about names defined from star imports
# flake8: noqa: F405

import copy
import sys

from .base import *  # noqa


DEBUG = True
LOG_DEBUG = False

ALLOWED_HOSTS = ['*']

# Log all emails to console
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Don't make life difficult for ourselves with password restrictions on dev
AUTH_PASSWORD_VALIDATORS = []

# Connecting to a Vagrant dev deploy for running experiments by default
CHASTE_URL = os.environ.get('CHASTE_URL', 'https://wl-backend.uksouth.cloudapp.azure.com/backend/fc_runner.py')
CHASTE_PASSWORD = os.environ.get('CHASTE_PASSWORD', 'nmc7--o-Lam-J3camDrolsFcu2A,GT')
CALLBACK_BASE_URL = os.environ.get('CALLBACK_BASE_URL', 'http://31.54.185.217:8001')

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


class InvalidStringShowWarning(str):
    def __mod__(self, other):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("In template, undefined variable or unknown value for: '%s'" % (other,))
        return ""


TEMPLATES[0]['OPTIONS']['string_if_invalid'] = InvalidStringShowWarning("%s")
