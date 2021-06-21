from .base import *  # noqa
try:
    # when running in deployed mode we need to import database setting to prevent access errors
    from .deployed import DATABASES  # noqa
except ImportError:
    # For CI tests we have no deployed settings
    pass


# Settings file used by pytest, whether locally or on Travis
