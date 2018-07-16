from django.contrib.auth.mixins import AccessMixin
from django.db.models import Q
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


def visibility_query(user):
    """Get a query filter for whether the given user can see something

    This also handles the case of non-logged-in users.
    """
    if user.is_authenticated:
        return Q(author=user) | ~Q(visibility=Visibility.PRIVATE)
    else:
        return Q(visibility=Visibility.PUBLIC)


def visibility_check(user, obj):
    """
    Object-based visibility check - can the user view the given object?

    :param: user to test against
    :param: the object - must have `visibility` and `author` fields
    :returns: True if the user is allowed to view the object, False otherwise
    """
    if user.is_authenticated:
        return obj.author == user or obj.visibility != Visibility.PRIVATE
    else:
        return obj.visibility == Visibility.PUBLIC


class VisibilityMixin(AccessMixin):
    """
    View mixin implementing visiblity restrictions

    Public objects can be seen by all.
    Restricted objects can be seen only by logged in users.
    Private objects can be seen only by their owner.

    If an object is not visible to a logged in user, we generate a 404
    If an object is not visible to an anonymous visitor, redirect to login page
    """

    def is_visible_to_anonymous(self, obj):
        # Anonymous user can only see public objects
        return obj and obj.visibility == Visibility.PUBLIC

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
        elif not self.is_visible_to_anonymous(obj):
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)
