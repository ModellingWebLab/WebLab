from .base import *  # noqa


DEBUG = True

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
    'root': BASE_DIR,  # noqa
}
