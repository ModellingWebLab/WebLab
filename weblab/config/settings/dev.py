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
    'root': str(BASE_DIR),  # noqa
}

# Connecting to a Vagrant dev deploy for running experiments by default
CHASTE_URL = os.environ.get('CHASTE_URL', 'http://localhost:8089/fc_runner.py')
CHASTE_PASSWORD = os.environ.get('CHASTE_PASSWORD', 'another secret password')
CALLBACK_BASE_URL = os.environ.get('CALLBACK_BASE_URL', 'http://10.0.2.2:8000')
