from .base import *  # noqa
try:
    from .deployed import DATABASES  # noqa
except ImportError:
    pass  # For CI tests we have no deployed settings


# Settings file used by pytest, whether locally or on Travis
