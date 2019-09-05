from django.conf import settings
from django.db import models
from guardian.shortcuts import assign_perm, get_users_with_perms, remove_perm

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

    def is_visibility_editable_by(self, user):
        """
        Is the entity's version visibility editable by the given user?

        :param user: User object
        :return: True if visibility editable, False otherwise
        """
        return user.is_superuser or user == self.author

    def is_editable_by(self, user):
        has_perm = user.has_perm('entities.create_{}'.format(self.entity_type))
        return has_perm and (
            user == self.author or
            user.has_perm('edit_entity', self)
        )

    def add_collaborator(self, user):
        assign_perm('edit_entity', user, self)

    def remove_collaborator(self, user):
        remove_perm('edit_entity', user, self)

    @property
    def collaborators(self):
        """
        All users who have specifically been permitted to collaborate on this object

        :return list of `User` objects
        """
        return [
            user
            for (user, perms) in get_users_with_perms(self, attach_perms=True).items()
            if 'edit_entity' in perms
        ]

    @property
    def viewers(self):
        """
        Users who have permission to view this object

        - i.e. the author and anybody listed as a collaborator

        This overrides the 'private' visibility for the object. A 'public'
        object is visible to all anyway.
        """
        return {
            user
            for user in self.collaborators
        } | {
            self.author
        }

    def is_managed_by(self, user):
        """
        Can the given user manage the entity (e.g. change permissions)
        """
        return user.is_superuser or user == self.author

    class Meta:
        abstract = True
