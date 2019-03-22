import binascii
import os
from datetime import datetime
from itertools import chain
from pathlib import Path
from shutil import rmtree
from tempfile import TemporaryDirectory

from django.utils.functional import cached_property
from django.utils.timezone import utc
from git import Actor, Blob, GitCommandError, Repo

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

        :return: `Commit` object
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
        Roll back repository to previous commit, removing untracked files
        """
        self._repo.head.reset('HEAD~', working_tree=True)
        for f in self.untracked_files:
            os.remove(os.path.join(self._root, f))

    @property
    def tag_dict(self):
        """
        Mapping of commits to git tags in the entity repository

        :return: dict of the form { 'commit_sha': ['tag_name'] }
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

        :return: `Commit` object or `None` if no commits
        """
        return Commit(self, self._repo.head.commit) if self._repo.head.is_valid() else None

    def get_commit(self, version):
        """
        Get commit object relating to version

        :param version: Reference to a commit

        :return `Commit` object
        """
        if version == 'latest':
            return self.latest_commit
        else:
            return Commit(self, self._repo.commit(version))

    @property
    def commits(self):
        """
        :return iterable of `Commit` objects in the entity repository
        """
        if self._repo.head.is_valid():
            return (Commit(self, c) for c in self._repo.iter_commits())
        else:
            return iter(())

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
    """
    Wrapper class for `git.Commit`
    """

    # This corresponds to the '--ref' parameter in `git notes` and allows
    # all weblab notes to be kept in their own store.
    NOTE_REF = 'weblab'

    # This notes ref is used for the list of ephemeral file names.
    FILE_LIST_REF = 'weblab-files-list'

    # This is the base notes ref for individual file contents. The file
    # name will be appended to it.
    FILE_REF_BASE = 'weblab-files/'

    def __init__(self, repo, commit):
        """
        :param repo: `Repository` object
        :param commit: `git.Commit` object
        """
        self._repo = repo
        self._commit = commit

    @cached_property
    def filenames(self):
        """
        All filenames in this commit

        :return: set of filenames
        """
        return {blob.name for blob in self._commit.tree.blobs} | self.ephemeral_file_names

    @property
    def files(self):
        """
        All files in this commit

        :return: iterable of `git.Blob` objects
        """
        return chain(self._commit.tree.blobs, self.ephemeral_files)

    def get_blob(self, filename):
        """
        Get a file from the commit in blob form

        :param filename: Name of file to retrieve
        :return: `git.Blob` object or None if file not found
        """
        for blob in self.files:
            if blob.name == filename:
                return blob

    def write_archive(self):
        """
        Create a Combine Archive of all files in this commit

        :return: file handle to archive
        """
        mtime = self.committed_at
        return ArchiveWriter().write(
            (blob.name, blob.data_stream, mtime) for blob in self.files
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
        return datetime.fromtimestamp(self._commit.committed_date).replace(tzinfo=utc)

    @cached_property
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

        :param note: Textual content of the note
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

    def add_ephemeral_file(self, name, content=None, path=None):
        """Add an ephemeral file as a git note.

        :param name: file name
        :param content: bytes object containing the file contents
        :param path: path to the file on disk

        One of content or path must be given.

        Raises ValueError if the name has already been used for a real or
        ephemeral file.
        """
        if name in self.filenames:
            raise ValueError("File name '{}' has already been used".format(name))
        cmd = self._repo._repo.git
        with TemporaryDirectory() as tmpdir:
            if path is None:
                # Write content to a temporary file
                assert content is not None
                path = os.path.join(tmpdir, name)
                with open(path, 'wb') as f:
                    f.write(content)
            # Store file in the git object DB
            obj_id = cmd.hash_object('-w', path)
            # Add this file to the list of ephemeral files for this commit
            cmd.notes('--ref', self.FILE_LIST_REF, 'append', '-m', name, self.hexsha)
            # Add the file as a note
            cmd.notes('--ref', self.FILE_REF_BASE + name, 'add', '-f', '-C', obj_id, self.hexsha)
        # Clear cached properties so they get recalculated on next access
        del self.ephemeral_file_names
        del self.filenames

    def get_ephemeral_file(self, name):
        """Get the contents of an ephemeral file as a Blob object.

        :param name: name of file to retrieve
        :return: `git.Blob` object or None if file not found
        """
        cmd = self._repo._repo.git
        try:
            blob_hexsha = cmd.notes('--ref', self.FILE_REF_BASE + name, 'list', self.hexsha)
            binsha = binascii.a2b_hex(blob_hexsha)
            return Blob(self._repo._repo, binsha, path=name)
        except GitCommandError:
            return None

    def list_ephemeral_files(self):
        """Get the names of any ephemeral files associated with this commit.

        :return: set of file names
        """
        cmd = self._repo._repo.git
        try:
            names_note = cmd.notes('--ref', self.FILE_LIST_REF, 'show', self.hexsha)
            return {n for n in names_note.split('\n') if n}
        except GitCommandError:
            return set()

    @property
    def ephemeral_files(self):
        """An iterable of `git.Blob` objects representing ephemeral files."""
        for name in self.ephemeral_file_names:
            yield self.get_ephemeral_file(name)

    @cached_property
    def ephemeral_file_names(self):
        return self.list_ephemeral_files()

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
