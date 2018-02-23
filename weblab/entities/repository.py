import os
from pathlib import Path
from shutil import rmtree

from django.utils.functional import cached_property
from git import Actor, Repo

from .manifest import ManifestReader, ManifestWriter


class Repository:
    """
    Wrapper class for `git.Repository`
    """

    def __init__(self, path):
        """
        :param path: Path of repository directory
        """
        self._root = str(path)

    def create(self):
        """
        Create an empty repository
        """
        Repo.init(self._root)

    def delete(self):
        """
        Delete the repository
        """
        rmtree(self._root)

    @cached_property
    def _repo(self):
        return Repo(self._root)

    def add_file(self, file_path):
        """
        Add a file to the repository

        :param file_path: Absolute path of file to be added
        """
        self._repo.index.add([str(file_path)])

    def rm_file(self, file_path):
        """
        Delete a file from the repository and working tree

        :param file_path: Absolute Path of file to be deleted
        """
        self._repo.index.remove([str(file_path)])
        Path(file_path).unlink()

    def commit(self, message, author):
        """
        Commit changes to the repository

        :param message: Commit message
        :param author: `User` who is authoring (and committing) the changes

        :return: `git.Commit` object
        """
        return self._repo.index.commit(
            message,
            author=Actor(author.full_name, author.email),
            committer=Actor(author.full_name, author.email),
        )

    def tag(self, tag, *, ref='HEAD'):
        """
        Tag the repository at the latest commit

        :param tag: Tag name to use
        :param ref: A reference to a specific commit, defaults to the latest
        """
        self._repo.create_tag(tag, ref=ref)

    @property
    def has_changes(self):
        """
        Are there changes that need to be committed?

        :returns: True if there are changes, False otherwise
        """
        return self._repo.is_dirty()

    @property
    def untracked_files(self):
        """
        :returns: list of untracked files in working tree
        """
        return self._repo.untracked_files

    def rollback(self):
        """
        Roll back repository to previous commit
        """
        self._repo.head.reset('HEAD~')

    @property
    def tag_dict(self):
        """
        Mapping of commits to git tags in the entity repository

        :return: dict of the form { `git.Commit`: ['tag_name'] }
        """
        tags = {}
        for tag in self._repo.tags:
            tags.setdefault(tag.commit, []).append(tag)
        return tags

    def hard_reset(self):
        """
        Reset the working tree
        """
        self._repo.head.reset(index=True, working_tree=True)

    @property
    def latest_commit(self):
        """
        Latest commit

        :return: `git.Commit` object or `None` if no commits
        """
        return self._repo.head.commit if self._repo.head.is_valid() else None

    def get_commit(self, version):
        """
        Get commit object relating to version

        :param version: Revision specification (sha, branch name, tag etc.)
            or 'latest' to get latest revision

        :return `git.Commit` object
        """
        if version == 'latest':
            return self.latest_commit
        else:
            return self._repo.commit(version)

    @property
    def commits(self):
        """
        :return iterable of `git.Commit` objects in the entity repository
        """
        return self._repo.iter_commits()

    @property
    def manifest_path(self):
        """
        Path of COMBINE manifest file

        :return: absolute path as a string
        """
        return os.path.join(self._root, 'manifest.xml')

    def generate_manifest(self, master_filename=None):
        """
        Generate COMBINE manifest file for repository index

        Stages the manifest file for commit. Will overwrite existing manifest.

        :param master_filename: Name of main/master file
        """
        writer = ManifestWriter()

        for entry in sorted(e for (e, _) in self._repo.index.entries):
            ext = ''.join(Path(entry).suffixes)[1:]
            writer.add_file(entry, ext, entry == master_filename)

        writer.write(self.manifest_path)
        self.add_file(self.manifest_path)

    @property
    def master_filename(self):
        """
        Get name of repository master file, as defined by COMBINE manifest

        :return: master filename, or None if no master file or no manifest
        """
        reader = ManifestReader()
        try:
            reader.read(self.manifest_path)
            return reader.master_filename
        except FileNotFoundError:
            pass

    def filenames(self, ref='HEAD'):
        """
        Get all filenames in repository

        :param ref: A reference to a specific commit, defaults to the latest
        :return: set of all filenames in repository
        """
        return {
            blob.name
            for blob in self.files(ref)
        }

    def files(self, ref='HEAD'):
        """
        Get all files in repository

        :param ref: A reference to a specific commit, defaults to the latest
        :return: iterable of all files in repository
        """
        return self._repo.commit(ref).tree.blobs
