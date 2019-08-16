import datetime
import uuid

import pytest
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.functions import Now
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from core import recipes
from entities.models import Entity
from repocache.models import CachedEntityVersion
from repocache.populate import populate_entity_cache
from datasets.models import Dataset


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
        commit = Helpers.fake_commit(entity.repo, 'file', User(full_name='author', email='author@example.com'))
        if tag_name:
            entity.repo.tag(tag_name)
        if visibility:
            entity.set_visibility_in_repo(commit, visibility)
        if cache:
            populate_entity_cache(entity)
        return commit

    @staticmethod
    def add_fake_version(entity, visibility, date=None):
        """Add a new commit/version only in the cache, not in git."""
        version = CachedEntityVersion.objects.create(
            entity=entity.repocache,
            sha=uuid.uuid4(),
            timestamp=date or Now(),
            visibility=visibility,
        )
        return version

    # Used to ensure each test commit has a different timestamp
    NEXT_COMMIT_TIMESTAMP = datetime.datetime(2010, 1, 1)

    @classmethod
    def fake_commit(cls, repo, message, author, date=None):
        """Make a test git commit with a fake date.

        This is identical to ``entities.repository.Repository.commit`` except
        that it allows the author & commit dates to be overridden. By default
        a numerically ascending sequence of timestamps will be used, 1 second
        apart, to ensure each test commit has a different timestamp.
        """
        from entities.repository import Actor, Commit
        if date is None:
            date = cls.NEXT_COMMIT_TIMESTAMP.isoformat()
            cls.NEXT_COMMIT_TIMESTAMP += datetime.timedelta(seconds=1)
        return Commit(repo, repo._repo.index.commit(
            message,
            author=Actor(author.full_name, author.email),
            author_date=date,
            committer=Actor(author.full_name, author.email),
            commit_date=date,
        ))

    @staticmethod
    def add_permission(user, perm, model=Entity):
        """Add permission to a user"""
        content_type = ContentType.objects.get_for_model(model)
        permission = Permission.objects.get(
            codename=perm,
            content_type=content_type,
        )
        user.user_permissions.add(permission)

    @staticmethod
    def login(client, user):
        client.login(username=user.email, password='password')

    @staticmethod
    def add_file(dataset, dataset_file):
        """Add a file to a dataset"""
        if not dataset.abs_path.exists():
            dataset.abs_path.mkdir()
        archive = str(dataset.abs_path / dataset.archive_name)
        open(archive, 'w').write(contents)
        # entity.repo.add_file(in_repo_path)
        # commit = Helpers.fake_commit(entity.repo, 'file', User(full_name='author', email='author@example.com'))
        # if tag_name:
        #     entity.repo.tag(tag_name)
        # if visibility:
        #     entity.set_visibility_in_repo(commit, visibility)
        # if cache:
        #     populate_entity_cache(entity)
        return dataset


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
def moderated_model(helpers):
    model = recipes.model.make()
    helpers.add_version(model, visibility='moderated')
    return model


@pytest.fixture
def moderated_protocol(helpers):
    protocol = recipes.protocol.make()
    helpers.add_version(protocol, visibility='moderated')
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
    version.mkdir()
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
def moderated_experiment_version(moderated_model, moderated_protocol):
    return recipes.experiment_version.make(
        status='SUCCESS',
        experiment__model=moderated_model,
        experiment__model_version=moderated_model.repo.latest_commit.hexsha,
        experiment__protocol=moderated_protocol,
        experiment__protocol_version=moderated_protocol.repo.latest_commit.hexsha,
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


@pytest.fixture
def moderator(user, helpers):
    helpers.add_permission(user, 'moderator')
    return user


@pytest.fixture
def dataset_creator(user, helpers):
    helpers.add_permission(user, 'create_dataset', Dataset)
    return user


@pytest.fixture
def dataset_no_files(dataset_creator, public_protocol):
    dataset = recipes.dataset.make(author=dataset_creator, name='mydataset', protocol=public_protocol)
    return dataset


@pytest.fixture
def dataset_with_file(user, public_protocol):
    dataset = recipes.dataset.make(author=user, name='mydataset', protocol=public_protocol)
    recipes.dataset_file.make(
        dataset=dataset,
        upload=SimpleUploadedFile('file1.csv', b'file 1'),
        original_name='file1.csv',
    )
    return dataset
