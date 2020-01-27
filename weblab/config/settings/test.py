from .base import TEMPLATES  # noqa


# Settings file used by pytest, whether locally or on Travis
class InvalidStringShowWarning(str):
    def __mod__(self, other):
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("In template, undefined variable or unknown value for: '%s'" % (other,))
        return ""


TEMPLATES[0]['OPTIONS']['string_if_invalid'] = InvalidStringShowWarning("%s")
