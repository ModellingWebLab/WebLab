import pytest

from accounts.models import User
from core import recipes


class Helpers:
    """
    Helper functions for tests - this can be passed into tests via a fixture
    """
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
    """
    Provide helpers in the form of a fixture
    """
    return Helpers


@pytest.fixture(autouse=True)
def fake_upload_path(settings, tmpdir):
    settings.MEDIA_ROOT = str(tmpdir)
    return settings.MEDIA_ROOT


@pytest.fixture(autouse=True)
def fake_experiment_path(settings, tmpdir):
    settings.EXPERIMENT_BASE = str(tmpdir)
    return settings.EXPERIMENT_BASE


@pytest.fixture(autouse=True)
def fake_repo_path(settings, tmpdir):
    settings.REPO_BASE = str(tmpdir)
    return settings.REPO_BASE


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
    version = recipes.experiment_version.make(
        status='QUEUED',
        experiment__model=model_with_version,
        experiment__protocol=protocol_with_version,
    )
    recipes.running_experiment.make(experiment_version=version)
    return version


@pytest.fixture
def experiment_version(model_with_version, protocol_with_version):
    return recipes.experiment_version.make(
        status='SUCCESS',
        experiment__model=model_with_version,
        experiment__model_version=model_with_version.repo.latest_commit.hexsha,
        experiment__protocol=protocol_with_version,
        experiment__protocol_version=protocol_with_version.repo.latest_commit.hexsha,
    )


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email='admin@example.com',
        full_name='Admin User',
        institution='UCL',
        password='password',
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


@pytest.fixture
def logged_in_admin(client, admin_user):
    client.login(username=admin_user.email, password='password')
    return admin_user
