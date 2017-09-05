from .base import *  # noqa


DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'dummy-secret-key'

ALLOWED_HOSTS = ['*']

# Log all emails to console
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Don't make life difficult for ourselves with password restrictions on dev
AUTH_PASSWORD_VALIDATORS = []
