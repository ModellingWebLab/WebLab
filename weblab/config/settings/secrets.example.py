# Example secrets file
# Copy to secrets.py and fill in the values

import os


# Create a unique random character string at least 50 characters long,
# e.g. with: import secrets; print(secrets.token_hex(50))
SECRET_KEY = ''

# Google OAuth2 - see http://code.google.com/apis/accounts/docs/OAuth2.html#Registering
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get('SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get('SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET', '')

# GitHub - see https://github.com/settings/applications/new
SOCIAL_AUTH_GITHUB_KEY = os.environ.get('SOCIAL_AUTH_GITHUB_KEY', '')
SOCIAL_AUTH_GITHUB_SECRET = os.environ.get('SOCIAL_AUTH_GITHUB_SECRET', '')

# Sign up for a free tier at https://rollbar.com/signup/
ROLLBAR_POST_SERVER_ITEM_ACCESS_TOKEN = ''
