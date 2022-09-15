from .base import *  # noqa
from .deployed import DATABASES  # noqa


# For running tests in a vagrant deployed environment
# run the test with `DJANGO_SETTINGS_MODULE=config.settings.vagrant` in pytest.ini
# This will use this file insetad of test.py
# You may also need to allow database creation on postgres, for changing permissions see: 
# https://stackoverflow.com/questions/10845998/i-forgot-the-password-i-entered-during-postgres-installation
# Make sure not to commit the modified pytest.ini!
