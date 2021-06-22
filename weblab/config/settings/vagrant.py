from .base import *  # noqa
from .deployed import DATABASES  # noqa


# For running tests in a vagrant deployed environment run the test with `DJANGO_SETTINGS_MODULE=vagrant` in pytest.ini
# This will use this file insetad of test.py
# Make sure not to commit the modified pytest.ini!
