import os
from datetime import datetime
from pathlib import Path
from shutil import rmtree

from django.utils.functional import cached_property
from git import Actor, GitCommandError, Repo

from core.combine import (
    MANIFEST_FILENAME,
    ArchiveWriter,
    ManifestReader,
    ManifestWriter,
)


class Repository:
    """
    Wrapper class for `git.Repo`
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
        return Commit(self, self._repo.index.commit(
            message,
            author=Actor(author.full_name, author.email),
            committer=Actor(author.full_name, author.email),
        ))

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
            tags.setdefault(tag.commit.hexsha, []).append(tag)
        return tags

    def get_name_for_commit(self, version):
        """Get a human-friendly display name for the given version

        :param version: Revision specification (sha, branch name, tag etc.)
            or 'latest' to get latest revision
        :return: tag for this commit, if any, or version if not
        """
        commit = self.get_commit(version)
        for tag in self._repo.tags:
            if tag.commit == commit._commit:
                return tag.name
        return version

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
        return Commit(self, self._repo.head.commit) if self._repo.head.is_valid() else None

    def get_commit(self, version):
        """
        Get commit object relating to version

        :param version: Reference to a commit

        :return `git.Commit` object
        """
        if version == 'latest':
            return self.latest_commit
        else:
            return Commit(self, self._repo.commit(version))

    @property
    def commits(self):
        """
        :return iterable of `git.Commit` objects in the entity repository
        """
        return (Commit(self, c) for c in self._repo.iter_commits())

    @property
    def manifest_path(self):
        """
        Path of COMBINE manifest file

        :return: absolute path as a string
        """
        return self.full_path(MANIFEST_FILENAME)

    def full_path(self, filename):
        """
        Return full filesystem path of file

        :param filename: filename
        :return: full absolute path of file
        """
        return os.path.join(self._root, filename)

    def generate_manifest(self, master_filename=None):
        """
        Generate COMBINE manifest file for repository index

        Stages the manifest file for commit. Will overwrite existing manifest.

        :param master_filename: Name of main/master file
        """
        writer = ManifestWriter()

        for entry in sorted(e for (e, _) in self._repo.index.entries):
            writer.add_file(entry, is_master=entry == master_filename)

        writer.write(self.manifest_path)
        self.add_file(self.manifest_path)


class Commit:
    NOTE_REF = 'weblab'

    def __init__(self, repo, commit):
        self._repo = repo
        self._commit = commit

    @property
    def filenames(self):
        """
        All filenames in this commit

        :return: set of all filenames in this commit
        """
        return {blob.name for blob in self.files}

    @property
    def files(self):
        """
        :return: iterable of all files in this commit
        """
        return self._commit.tree.blobs

    def get_blob(self, filename, ref='HEAD'):
        """
        Get a file from the commit in blob form

        :param filename: Name of file to retrieve
        :return: `git.Blob` object or none if file not found
        """
        for blob in self.files:
            if blob.name == filename:
                return blob

    def write_archive(self):
        """
        Create a Combine Archive of all files in this commit

        :return: file handle to archive
        """
        return ArchiveWriter().write(
            (self._repo.full_path(fn), fn) for fn in self.filenames
        )

    @property
    def hexsha(self):
        """
        SHA of the commit

        :return: hex string of the commit's SHA
        """
        return self._commit.hexsha

    @property
    def author(self):
        """
        Author of the commit

        :return: String containing author name
        """
        return self._commit.author

    @property
    def message(self):
        """
        Commit message

        :return: String containing commit message
        """
        return self._commit.message

    def __eq__(self, other):
        return other._commit == self._commit

    @property
    def committed_at(self):
        """
        Datetime representation of commit timestamp

        :return: `datetime` object
        """
        return datetime.fromtimestamp(self._commit.committed_date)

    @property
    def master_filename(self):
        """
        Get name of master file on this commit, as defined by COMBINE manifest

        :return: master filename, or None if no master file or no manifest
        """
        reader = ManifestReader()
        for file_ in self.files:
            if file_.name == MANIFEST_FILENAME:
                reader.read(file_.data_stream)

        return reader.master_filename

    def add_note(self, note):
        """
        Add a git note to this commit

        :param: Textual content of the note
        """
        cmd = self._repo._repo.git
        cmd.notes('--ref', self.NOTE_REF, 'add', '-f', '-m', note, self.hexsha)

    def get_note(self):
        """
        Get the git note of this commit

        :return: Textual content of the note, or None if there is no note
        """
        cmd = self._repo._repo.git
        try:
            return cmd.notes('--ref', self.NOTE_REF, 'show', self.hexsha)
        except GitCommandError:
            return None

    @property
    def parents(self):
        return (
            Commit(self._repo, parent)
            for parent in self._commit.iter_parents()
        )

    @property
    def self_and_parents(self):
        yield self
        yield from self.parents
