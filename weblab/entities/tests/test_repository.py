import os.path
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from git import GitCommandError

from accounts.models import User
from entities.repository import Repository


@pytest.fixture
def repo(tmpdir):
    return Repository(tmpdir)


@pytest.fixture
def repo_file(repo):
    repo.create()
    path = os.path.join(repo._root, 'file.cellml')
    with open(path, 'w') as f:
        f.write('file contents')
    return Path(path)


@pytest.fixture
def author():
    return User(full_name='Commit Author', email='author@example.com')


@pytest.fixture
def commit(repo, repo_file, author):
    repo.add_file(repo_file)
    commit = repo.commit('commit 1', author)
    return commit


class TestRepository:
    def test_create_and_delete(self, repo):
        repo.create()
        assert (Path(repo._root) / '.git').exists()

        repo.delete()
        assert not Path(repo._root).exists()

    def test_add_and_rm_file(self, repo, repo_file):
        repo.add_file(repo_file)
        # the 0 means the file is staged
        assert (repo_file.name, 0) in repo._repo.index.entries

        repo.rm_file(repo_file)
        assert len(repo._repo.index.entries) == 0
        assert not repo_file.exists()

    def test_commit(self, repo, repo_file, author):
        assert list(repo.commits) == []
        assert repo.latest_commit is None

        repo.add_file(repo_file)
        repo.commit('commit_message', author)

        assert len(list(repo.commits)) == 1
        assert next(repo.latest_commit.files).name == repo_file.name
        assert repo.latest_commit.author.email == author.email

    def test_tag(self, repo, repo_file, author):
        repo.add_file(repo_file)
        commit = repo.commit('commit_message', author)

        repo.tag('v1')

        assert repo.tag_dict[commit.hexsha][0].name == 'v1'

        # A tag cannot be reused / moved
        repo.commit('second commit', author)
        with pytest.raises(GitCommandError):
            repo.tag('v1')

    def test_name_for_commit(self, repo, repo_file, author):
        repo.add_file(repo_file)
        commit = repo.commit('commit_message', author)

        assert repo.get_name_for_commit(commit.hexsha) == commit.hexsha
        assert repo.get_name_for_commit('latest') == 'latest'

        repo.tag('v1')

        assert repo.get_name_for_commit(commit.hexsha) == 'v1'
        assert repo.get_name_for_commit('v1') == 'v1'
        assert repo.get_name_for_commit('latest') == 'v1'

    def test_has_changes(self, repo, repo_file, author):
        assert not repo.has_changes
        repo.add_file(repo_file)
        assert repo.has_changes
        repo.commit('commit_message', author)
        assert not repo.has_changes

    def test_untracked_files(self, repo, repo_file):
        assert repo_file.name in repo.untracked_files
        repo.add_file(repo_file)
        assert repo_file.name not in repo.untracked_files

    def test_rollback(self, repo, repo_file, author):
        repo.add_file(repo_file)
        commit1 = repo.commit('commit 1', author)
        open(str(repo_file), 'w').write('updated contents')
        repo.add_file(repo_file)
        commit2 = repo.commit('commit 2', author)
        assert repo.latest_commit == commit2
        untracked_file = Path(repo._root) / 'untracked.txt'
        untracked_file.open('w').write('contents')
        assert untracked_file.exists()
        repo.rollback()
        assert repo.latest_commit == commit1
        assert repo_file.open().read() == 'file contents'
        assert not untracked_file.exists()

    def test_hard_reset(self, repo, repo_file):
        repo.add_file(repo_file)
        assert repo.has_changes
        repo.hard_reset()
        assert not repo.has_changes

    def test_get_commit(self, repo, repo_file, author):
        repo.add_file(repo_file)
        commit = repo.commit('commit 1', author)
        assert repo.latest_commit == commit
        assert repo.get_commit(commit.hexsha) == commit
        assert repo.get_commit('latest') == commit
        assert next(repo.commits) == commit

    def test_generate_manifest(self, repo, repo_file, author):
        repo.add_file(repo_file)

        path = Path(repo._root) / 'file2.cellml'
        open(str(path), 'w').write('file2 contents')
        repo.add_file(path)

        repo.generate_manifest(master_filename='file.cellml')

        manifest_file = Path(repo._root) / 'manifest.xml'
        root = ET.parse(str(manifest_file)).getroot()
        assert [child.attrib['location'] for child in root] == ['file.cellml', 'file2.cellml']
        assert [child.attrib['format'] for child in root] == [
            'http://identifiers.org/combine.specifications/cellml',
            'http://identifiers.org/combine.specifications/cellml',
        ]

        commit = repo.commit('commit 1', author)
        assert commit.master_filename == 'file.cellml'


class TestCommit:
    def test_files(self, repo, repo_file, author):
        repo.add_file(repo_file)
        commit = repo.commit('commit 1', author)
        repo.generate_manifest()

        assert list(commit.filenames) == ['file.cellml']
        assert commit.get_blob('file.cellml').data_stream.read().decode() == 'file contents'
        assert commit.get_blob('nonexistent.cellml') is None

    def test_write_archive(self, repo, repo_file, author):
        repo.add_file(repo_file)
        repo.generate_manifest()
        repo.commit('commit 1', author)

        archive = repo.get_commit('latest').write_archive()
        assert zipfile.ZipFile(archive).namelist() == ['file.cellml', 'manifest.xml']

    def test_write_archive_for_old_version(self, repo, repo_file, author):
        # Initial commit
        repo.add_file(repo_file)
        repo.generate_manifest()
        v1 = repo.commit('commit 1', author)
        old_contents = repo_file.open().read().encode('UTF-8')

        # Change file contents
        with repo_file.open('w') as f:
            f.write('new contents')
        repo.add_file(repo_file)
        repo.commit('commit 2', author)

        # Write archive for commit 1
        archive = v1.write_archive()
        zf = zipfile.ZipFile(archive)
        assert zf.namelist() == ['file.cellml', 'manifest.xml']
        assert zf.open('file.cellml').read() == old_contents

    def test_master_filename_is_none_if_no_manifest(self, repo, repo_file, author):
        repo.add_file(repo_file)
        commit = repo.commit('commit 1', author)
        assert commit.master_filename is None

    def test_master_filename_is_none_if_none_selected(self, repo, repo_file, author):
        repo.add_file(repo_file)
        commit = repo.commit('commit 1', author)
        repo.generate_manifest()

        assert commit.master_filename is None

    def test_notes(self, commit):
        assert commit.get_note() is None
        commit.add_note('Visibility: private')
        assert commit.get_note() == 'Visibility: private'

    def test_properties(self, repo, repo_file, author):
        repo.add_file(repo_file)
        commit = repo.commit('commit 1', author)
        assert commit.author.name == author.full_name
        assert commit.author.email == author.email
        assert commit.hexsha == commit._commit.hexsha
        assert commit.message == 'commit 1'

    def test_parents(self, repo, repo_file, author):
        repo.add_file(repo_file)
        commit1 = repo.commit('commit 1', author)

        open(str(repo_file), 'w').write('updated contents')
        repo.add_file(repo_file)
        commit2 = repo.commit('commit 2', author)

        assert list(commit2.parents) == [commit1]
        assert list(commit2.self_and_parents) == [commit2, commit1]

    def test_add_and_get_ephemeral_file(self, repo, author):
        repo.create()
        commit = repo.commit('commit 1', author)
        content = b'readme content'
        name = 'readme.md'

        assert commit.filenames == set()
        assert commit.list_ephemeral_files() == set()
        assert commit.ephemeral_file_names == set()
        commit.add_ephemeral_file(name, content)
        assert commit.list_ephemeral_files() == {name}
        assert commit.ephemeral_file_names == {name}
        assert commit.get_ephemeral_file(name).data_stream.read() == content
        e_files = list(commit.ephemeral_files)
        assert len(e_files) == 1
        assert e_files[0].data_stream.read() == content

        assert commit.filenames == {name}
        assert list(commit.files) == list(e_files)
        assert commit.get_blob(name) == commit.get_ephemeral_file(name)

    def test_ephemeral_and_normal_files(self, repo, repo_file, author):
        # We make a commit with a normal file
        repo.add_file(repo_file)
        commit = repo.commit('commit 1', author)
        assert commit.filenames == {'file.cellml'}

        # We add 2 ephemeral files
        content1 = b'readme content'
        name1 = 'readme.md'
        commit.add_ephemeral_file(name1, content1)

        content2 = b'errors content'
        name2 = 'errors.txt'
        commit.add_ephemeral_file(name2, content2)

        # All 3 files are listed as present
        assert commit.ephemeral_file_names == {name1, name2}
        assert commit.get_ephemeral_file(name1).data_stream.read() == content1
        assert commit.get_ephemeral_file(name2).data_stream.read() == content2

        assert commit.filenames == {name1, name2, 'file.cellml'}
        assert commit.get_blob(name1) == commit.get_ephemeral_file(name1)
        assert commit.get_blob(name2) == commit.get_ephemeral_file(name2)

        for f in commit.files:
            assert f.name in {name1, name2, 'file.cellml'}
            if f.name == name1:
                assert f.data_stream.read() == content1
            elif f.name == name2:
                assert f.data_stream.read() == content2
            else:
                assert f.data_stream.read() == b'file contents'

    def test_ephemeral_files_do_not_persist(self, repo, repo_file, author):
        # We add an ephemeral file to the first commit
        repo.create()
        commit1 = repo.commit('commit 1', author)
        content = b'readme content'
        name = 'readme.md'
        commit1.add_ephemeral_file(name, content)

        # We make a new commit
        repo.add_file(repo_file)
        commit2 = repo.commit('commit 2', author)

        # The ephemeral file does not appear in the latest version
        assert commit2.ephemeral_file_names == set()
        assert commit2.filenames == {'file.cellml'}

        # The ephemeral file still appears in the original commit
        assert commit1.ephemeral_file_names == {name}
        assert commit1.filenames == {name}
        assert commit1.get_ephemeral_file(name).data_stream.read() == content

    def test_ephemeral_name_repeat_error(self, commit):
        name = 'readme.md'
        commit.add_ephemeral_file(name, b'content 1')
        with pytest.raises(ValueError):
            commit.add_ephemeral_file(name, b'content 2')

    def test_ephemeral_name_matches_real_file_error(self, commit):
        with pytest.raises(ValueError):
            commit.add_ephemeral_file('file.cellml', b'content')

    def test_get_missing_ephemeral_file(self, commit):
        assert commit.get_ephemeral_file('not-present.md') is None
