from django.contrib.auth.mixins import AccessMixin
from django.http import Http404


class Visibility:
    PRIVATE = 'private'
    PUBLIC = 'public'


HELP_TEXT = (
    'Public = anyone can view\n'
    'Private = only you can view'
)

CHOICES = (
    (Visibility.PRIVATE, 'Private'),
    (Visibility.PUBLIC, 'Public')
)


def get_joint_visibility(*visibilities):
    """
    :return: joint visibility of a set of visibilities
    """
    # Ordered by most conservative first
    levels = [
        Visibility.PRIVATE, Visibility.PUBLIC,
    ]

    # Use the most conservative of the two entities' visibilities
    return levels[min(
        levels.index(vis)
        for vis in visibilities
    )]


def visible_entity_ids(user):
    """
    Get IDs of entities which are visible to the given user

    :return: set of entity IDs
    """
    from entities.models import ModelEntity, ProtocolEntity
    from repocache.entities import get_public_entity_ids

    public_entity_ids = get_public_entity_ids()

    if user.is_authenticated:
        # Get the user's own entities and those they have permission for
        visible = user.entity_set.all().union(
            ModelEntity.objects.with_edit_permission(user),
            ProtocolEntity.objects.with_edit_permission(user),
        )
        visible_ids = set(visible.values_list('id', flat=True))

        return public_entity_ids | visible_ids
    else:
        return public_entity_ids


def visibility_check(visibility, allowed_users, user):
    """
    Visibility check

    :param visibility: `Visibility` value
    :param allowed_users: Users that have special privileges in this scenario
    :param: user: user to test against

    :returns: True if the user has permission to view, False otherwise
    """
    allow_access = False

    if visibility == Visibility.PUBLIC:
        # Public is visible to everybody
        return True

    elif user.is_authenticated:
        # Logged in user can view all except other people's private stuff
        return (
            user in allowed_users or
            visibility != Visibility.PRIVATE
        )


class VisibilityMixin(AccessMixin):
    """
    View mixin implementing visiblity restrictions

    Public objects can be seen by all.
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
