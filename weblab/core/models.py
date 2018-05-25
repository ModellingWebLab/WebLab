from django.conf import settings
from django.db import models

from . import visibility


class VisibilityModelMixin(models.Model):
    """
    Model mixin for giving objects different levels of visibility
    """
    visibility = models.CharField(
        max_length=16,
        choices=visibility.CHOICES,
        help_text=visibility.HELP_TEXT.replace('\n', '<br />'),
    )

    class Meta:
        abstract = True


class UserCreatedModelMixin(models.Model):
    """
    Model mixin for user-created objects
    """
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL)

    def is_deletable_by(self, user):
        """
        Is the entity deletable by the given user?

        :param user: User object
        :return: True if deletable, False otherwise
        """
        return user.is_superuser or user == self.author

    class Meta:
        abstract = True
