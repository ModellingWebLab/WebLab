from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from accounts.models import User
from entities.repository import Repository


@pytest.fixture
def repo(tmpdir):
    return Repository(tmpdir)


@pytest.fixture
def repo_file(repo):
    repo.create()
    path = Path(repo._root) / 'file.cellml'
    path.write_text('file contents')
    return path


@pytest.fixture
def author():
    return User(full_name='Commit Author', email='author@example.com')


class TestRepository:
    def test_create_and_delete(self, repo):
        repo.create()
        assert (Path(repo._root) / '.git').exists()

        repo.delete()
        assert not Path(repo._root).exists()

    def test_add_and_rm_file(self, repo, repo_file):
        repo.add_file(repo_file)
        # the 0 means whether the file is staged
        assert (repo_file.name, 0) in repo._repo.index.entries

        repo.rm_file(repo_file)
        assert len(repo._repo.index.entries) == 0
        assert not repo_file.exists()

    def test_commit(self, repo, repo_file, author):
        repo.add_file(repo_file)

        repo.commit('commit_message', author)

        assert repo.latest_commit.author.email == author.email

    def test_tag(self, repo, repo_file, author):
        repo.add_file(repo_file)
        commit = repo.commit('commit_message', author)

        repo.tag('v1')

        assert repo.tag_dict[commit][0].name == 'v1'

    def test_has_changes(self, repo, repo_file, author):
        assert not repo.has_changes
        repo.add_file(repo_file)
        assert repo.has_changes
        repo.commit('commit_message', author)
        assert not repo.has_changes

    def test_untracked_files(self, repo, repo_file):
        assert repo_file.name in repo.untracked_files

    def test_rollback(self, repo, repo_file, author):
        repo.add_file(repo_file)
        commit1 = repo.commit('commit 1', author)
        repo_file.write_text('updated contents')
        repo.add_file(repo_file)
        commit2 = repo.commit('commit 2', author)
        assert repo.latest_commit == commit2
        repo.rollback()
        assert repo.latest_commit == commit1

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

    def test_generate_manifest(self, repo, repo_file):
        repo.add_file(repo_file)

        path = Path(repo._root) / 'file2.cellml'
        path.write_text('file2 contents')
        repo.add_file(path)

        repo.generate_manifest(master_filename='file.cellml')

        manifest_file = Path(repo._root) / 'manifest.xml'
        root = ET.parse(str(manifest_file)).getroot()
        assert [child.attrib['location'] for child in root] == ['file.cellml', 'file2.cellml']
        assert repo.master_filename == 'file.cellml'

    def test_master_filename_is_none_if_no_manifest(self, repo):
        assert repo.master_filename is None

    def test_master_filename_is_none_if_none_selected(self, repo, repo_file):
        repo.add_file(repo_file)
        repo.generate_manifest()

        assert repo.master_filename is None
