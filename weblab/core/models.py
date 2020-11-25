import urllib.parse

from django.conf import settings
from django.db import models
from django.urls import reverse
from guardian.shortcuts import assign_perm, get_users_with_perms, remove_perm

from . import visibility
from .combine import ArchiveReader


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
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

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
            user.has_perm('entities.edit_entity', self)
        )

    def add_collaborator(self, user):
        assign_perm('entities.edit_entity', user, self)

    def remove_collaborator(self, user):
        remove_perm('entities.edit_entity', user, self)

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


class FileCollectionMixin:
    """Mixin for DB models that represent collections of files backed by a COMBINE Archive.

    This doesn't provide any DB fields, but does define common properties and methods for
    such collections, ensuring they present a consistent API.
    """
    @property
    def abs_path(self):
        """The folder where the backing archive is stored on disk.

        Must be defined by subclasses.
        """
        raise NotImplementedError

    @property
    def archive_name(self):
        """The name of the backing archive.

        Must be defined by subclasses.
        """
        raise NotImplementedError

    @property
    def archive_path(self):
        """The full path to the backing archive. A ``pathlib.Path`` instance."""
        return self.abs_path / self.archive_name

    @property
    def files(self):
        """The list of files (``core.combine.ArchiveFile`` instances) contained in this archive."""
        if self.archive_path.exists():
            return ArchiveReader(str(self.archive_path)).files
        else:
            return []

    @property
    def master_file(self):
        """Get the master file, or the first file if there is only one
        """
        if len(self.files) == 1:
            return self.files[0]
        else:
            return next((f for f in self.files if f.is_master), None)

    def mkdir(self):
        """Create the folder for the backing archive (and parents if needed)."""
        self.abs_path.mkdir(exist_ok=True, parents=True)

    def open_file(self, name):
        """Open the given file in the archive for reading."""
        return ArchiveReader(str(self.archive_path)).open_file(name)

    def get_file_json(self, file_, ns, url_args):
        """Get information about a file in JSON format for use by Javascript code.

        :param core.combine.ArchiveFile file_: the file to provide info about
        :param str ns: the app namespace to use for reversing download URLs
        :param list url_args: initial argument(s) for reverse to identify the collection the file is in
        :return: a dictionary of file metadata
        """
        return {
            'id': file_.name,
            'author': self.author.full_name,
            'created': self.created_at,
            'name': file_.name,
            'filetype': file_.fmt,
            'masterFile': file_.is_master,
            'size': file_.size,
            'url': reverse(
                ns + ':file_download',
                args=url_args + [urllib.parse.quote(file_.name)]
            )
        }

    def get_json(self, ns, url_args):
        """Get information about this collection in JSON format for use by Javascript code.

        :param str ns: the app namespace to use for reversing download URLs
        :param list url_args: initial argument(s) for reverse to identify this collection
        :return: a dictionary of collection metadata, including info about each file
        """
        files = [
            self.get_file_json(f, ns, url_args)
            for f in self.files
            if f.name not in ['manifest.xml', 'metadata.rdf']
        ]
        return {
            'id': self.id,
            'author': self.author.full_name,
            'parsedOk': False,
            'visibility': self.visibility,
            'created': self.created_at,
            'name': self.name,
            'files': files,
            'numFiles': len(files),
            'download_url': reverse(ns + ':archive', args=url_args),
        }
