from django.contrib.auth.mixins import AccessMixin
from django.db import models
from django.http import Http404


class Visibility:
    PRIVATE = 'private'
    RESTRICTED = 'restricted'
    PUBLIC = 'public'


HELP_TEXT = (
    'Public = anyone can view\n'
    'Restricted = logged in users can view\n'
    'Private = only you can view'
)

CHOICES = (
    (Visibility.PRIVATE, 'Private'),
    (Visibility.RESTRICTED, 'Restricted'),
    (Visibility.PUBLIC, 'Public')
)


def get_joint_visibility(*visibilities):
    """
    :return: joint visibility of a set of visibilities
    """
    # Ordered by most conservative first
    levels = [
        Visibility.PRIVATE, Visibility.RESTRICTED, Visibility.PUBLIC,
    ]

    # Use the most conservative of the two entities' visibilities
    return levels[min(
        levels.index(vis)
        for vis in visibilities
    )]


class VisibilityMixin(AccessMixin):
    """
    View mixin implementing visiblity restrictions

    Public objects can be seen by all.
    Restricted objects can be seen only by logged in users.
    Private objects can be seen only by their owner.

    If an object is not visible to a logged in user, we generate a 404
    If an object is not visible to an anonymous visitor, redirect to login page
    """

    def dispatch(self, request, *args, **kwargs):
        # We don't necessarily want 'object not found' to give a 404 response
        # (if the user is anonymous it makes more sense to login-redirect them)
        try:
            obj = self.get_object()
        except Http404:
            obj = None

        if self.request.user.is_authenticated():
            # Logged in user can view all except other people's private stuff
            if not obj or (
                obj.author != self.request.user and
                obj.visibility == Visibility.PRIVATE
            ):
                raise Http404
        else:
            # Anonymous user can only see public objects
            if not obj or (obj.visibility != Visibility.PUBLIC):
                return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)


class VisibilityModelMixin(models.Model):
    """
    Model mixin for giving objects different levels of visibility
    """
    visibility = models.CharField(
        max_length=16,
        choices=CHOICES,
        help_text=HELP_TEXT.replace('\n', '<br />'),
    )

    class Meta:
        abstract = True
