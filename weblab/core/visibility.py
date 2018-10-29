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


def visible_entity_ids(user):
    """
    Get IDs of entities which are visible to the given user

    :return: set of entity IDs
    """
    from repocache.entities import get_public_entity_ids, get_restricted_entity_ids

    public_entity_ids = get_public_entity_ids()

    if user.is_authenticated:
        user_entity_ids = set(user.entity_set.values_list('id', flat=True))
        non_public_entity_ids = get_restricted_entity_ids() | user_entity_ids

        return public_entity_ids | non_public_entity_ids
    else:
        return public_entity_ids


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

    def get_owner(self):
        """
        Get the owner applicable to the visibility restrictions on this view

        :return: `User` object
        """
        return self.get_object().author

    def dispatch(self, request, *args, **kwargs):
        # We want to treat "not visible" the same way as "does not exist" -
        # so defer any exception handling until later
        try:
            obj = self.get_object()
        except Http404:
            obj = None

        allow_access = False

        if obj:
            visibility = self.get_visibility()
            owner = self.get_owner()
            if visibility == Visibility.PUBLIC:
                allow_access = True

            if self.request.user.is_authenticated:
                # Logged in user can view all except other people's private stuff
                allow_access = (
                    owner == self.request.user or
                    visibility != Visibility.PRIVATE
                )
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
            # For logged in user, raise a 404
            return self.handle_no_permission()

