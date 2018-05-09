import pytest

from accounts.models import User
from core import recipes


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


@pytest.fixture
def model_with_version():
    model = recipes.model.make()
    Helpers.add_version(model)
    return model


@pytest.fixture
def protocol_with_version():
    protocol = recipes.protocol.make()
    Helpers.add_version(protocol)
    return protocol


@pytest.fixture
def queued_experiment(model_with_version, protocol_with_version):
    return recipes.experiment_version.make(
        status='QUEUED',
        experiment__model=model_with_version,
        experiment__protocol=protocol_with_version,
    )


@pytest.fixture
def experiment(model_with_version, protocol_with_version):
    return recipes.experiment_version.make(
        status='SUCCESS',
        experiment__model=model_with_version,
        experiment__protocol=protocol_with_version,
    )


@pytest.fixture
def user():
    return User.objects.create_user(
        email='test@example.com',
        full_name='Test User',
        institution='UCL',
        password='password',
    )


@pytest.fixture
def other_user():
    return User.objects.create_user(
        email='other@example.com',
        full_name='Other User',
        institution='UCL',
        password='password',
    )


@pytest.fixture
def logged_in_user(client, user):
    client.login(username=user.email, password='password')
    return user
