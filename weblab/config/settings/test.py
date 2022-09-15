from .base import *  # noqa


# Settings file used by pytest, whether locally or on github actions
# For running tests in a vagrant deployed environment
# run the test with `DJANGO_SETTINGS_MODULE=config.settings.vagrant` in pytest.ini
# You may also need to allow database creation on postgres, for changing permissions see:
# https://stackoverflow.com/questions/10845998/i-forgot-the-password-i-entered-during-postgres-installation
# (see vagrant.py)
# Make sure not to commit the modified pytest.ini!
