import pytest
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType

from accounts.models import User
from core import recipes
from entities.models import Entity
from repocache.populate import populate_entity_cache


class Helpers:
    """
    Helper functions for tests - this can be passed into tests via a fixture
    """
    @staticmethod
    def add_version(entity,
                    filename='file1.txt',
                    tag_name=None,
                    visibility=None,
                    cache=True,
                    contents='entity contents'):
        """Add a single commit/version to an entity"""
        entity.repo.create()
        in_repo_path = str(entity.repo_abs_path / filename)
        open(in_repo_path, 'w').write(contents)
        entity.repo.add_file(in_repo_path)
        commit = entity.repo.commit('file', User(full_name='author', email='author@example.com'))
        if tag_name:
            entity.repo.tag(tag_name)
        if visibility:
            entity.set_visibility_in_repo(commit, visibility)
        if cache:
            populate_entity_cache(entity)
        return commit

    @staticmethod
    def add_permission(user, perm):
        """Add permission to a user"""
        content_type = ContentType.objects.get_for_model(Entity)
        permission = Permission.objects.get(
            codename=perm,
            content_type=content_type,
        )
        user.user_permissions.add(permission)

    @staticmethod
    def login(client, user):
        client.login(username=user.email, password='password')


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
    Helpers.add_version(model, visibility='private')
    return model


@pytest.fixture
def protocol_with_version():
    protocol = recipes.protocol.make()
    Helpers.add_version(protocol, visibility='private')
    return protocol


@pytest.fixture
def public_model(helpers):
    model = recipes.model.make()
    helpers.add_version(model, visibility='public')
    return model


@pytest.fixture
def public_protocol(helpers):
    protocol = recipes.protocol.make()
    helpers.add_version(protocol, visibility='public')
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
def experiment_with_result(model_with_version, protocol_with_version):
    version = recipes.experiment_version.make(
        status='SUCCESS',
        experiment__model=model_with_version,
        experiment__protocol=protocol_with_version,
    )
    version.abs_path.mkdir()
    with (version.abs_path / 'result.txt').open('w') as f:
        f.write('experiment results')
    return version



@pytest.fixture
def experiment_version(public_model, public_protocol):
    return recipes.experiment_version.make(
        status='SUCCESS',
        experiment__model=public_model,
        experiment__model_version=public_model.repo.latest_commit.hexsha,
        experiment__protocol=public_protocol,
        experiment__protocol_version=public_protocol.repo.latest_commit.hexsha,
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
def anon_user():
    return AnonymousUser()


@pytest.fixture
def logged_in_user(client, user):
    client.login(username=user.email, password='password')
    return user


@pytest.fixture
def logged_in_admin(client, admin_user):
    client.login(username=admin_user.email, password='password')
    return admin_user


@pytest.fixture
def model_creator(user, helpers):
    helpers.add_permission(user, 'create_model')
    return user
