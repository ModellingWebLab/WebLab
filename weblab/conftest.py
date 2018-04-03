import pytest

from accounts.models import User


class Helpers:
    @staticmethod
    def add_version(entity, filename='file1.txt', tag_name=None):
        """Add a single commit/version to an entity"""
        entity.repo.create()
        in_repo_path = str(entity.repo_abs_path / filename)
        open(in_repo_path, 'w').write('entity contents')
        entity.repo.add_file(in_repo_path)
        commit = entity.repo.commit('file', User(full_name='author', email='author@example.com'))
        if tag_name:
            entity.repo.tag(tag_name)
        return commit


@pytest.fixture
def helpers():
    return Helpers
