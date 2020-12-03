from django.contrib.auth.mixins import AccessMixin
from django.http import Http404


class Visibility:
    PRIVATE = 'private'
    PUBLIC = 'public'
    MODERATED = 'moderated'


HELP_TEXT = (
    'Moderated = public and checked by a moderator\n'
    'Public = anyone can view\n'
    'Private = only you can view'
)

CHOICES = (
    (Visibility.PRIVATE, 'Private'),
    (Visibility.PUBLIC, 'Public'),
    (Visibility.MODERATED, 'Moderated'),
)

# Ordered by most conservative first
LEVELS = [
    Visibility.PRIVATE,
    Visibility.PUBLIC,
    Visibility.MODERATED,
]

VISIBILITY_LEVEL_MAP = {vis: LEVELS.index(vis) for vis in LEVELS}


def get_joint_visibility(*visibilities):
    """
    :return: joint visibility of a set of visibilities
    """
    # Use the most conservative of the two entities' visibilities
    return LEVELS[min(
        VISIBILITY_LEVEL_MAP[vis]
        for vis in visibilities
    )]


def visibility_meets_threshold(visibility, threshold):
    """Test whether a given visibility is at least at the threshold.

    For instance if the threshold is 'public' then 'moderated' is also OK.

    :param visibility: the visibility to test
    :param threshold: the minimum visibility allowed, or None if anything goes
    """
    if threshold is None:
        threshold = Visibility.PRIVATE
    return VISIBILITY_LEVEL_MAP[visibility] >= VISIBILITY_LEVEL_MAP[threshold]


def visibility_check(visibility, allowed_users, user):
    """
    Visibility check

    :param visibility: `Visibility` value
    :param allowed_users: Users that have special privileges in this scenario
    :param: user: user to test against

    :returns: True if the user has permission to view, False otherwise
    """
    if visibility in [Visibility.PUBLIC, Visibility.MODERATED]:
        # Public and moderated are visible to everybody
        return True

    elif user.is_authenticated:
        # Logged in user can view all except other people's private stuff
        # unless given special permissions to do so
        return (
            user in allowed_users or
            visibility != Visibility.PRIVATE
        )

    return False


class VisibilityMixin(AccessMixin):
    """
    View mixin implementing visiblity restrictions

    Public and moderated objects can be seen by all.
    Private objects can be seen only by their owner.

    If an object is not visible to a logged in user, we generate a 404
    If an object is not visible to an anonymous visitor, redirect to login page
    """

    def check_access_token(self, token):
        """
        Check an access token passed in by HTTP header.
        By default, token access is not allowed. Certain views can override
        this.
        """
        return False  # Token access not used by default

    def get_visibility(self):
        """
        Get the visibility applicable to this view

        :return: string representing visibility
        """
        return self.get_object().visibility

    def get_viewers(self):
        """
        Get users who are permitted to view the object regardless of visibility

        :return: set of `User` objects
        """
        return self.get_object().viewers

    def dispatch(self, request, *args, **kwargs):
        # We want to treat "not visible" the same way as "does not exist" -
        # so defer any exception handling until later
        try:
            obj = self.get_object()
        except Http404:
            obj = None

        allow_access = False

        if obj:
            if visibility_check(self.get_visibility(),
                                self.get_viewers(),
                                self.request.user):
                allow_access = True
            else:
                auth_header = self.request.META.get('HTTP_AUTHORIZATION')
                if auth_header and auth_header.startswith('Token'):
                    token = auth_header[5:].strip()
                    allow_access = self.check_access_token(token)

        if allow_access:
            return super().dispatch(request, *args, **kwargs)

        elif self.request.user.is_authenticated:
            # For logged in user, raise a 404
            raise Http404
        else:
            # For anonymous user, redirect to login page
            return self.handle_no_permission()
