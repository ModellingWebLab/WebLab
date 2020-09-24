import datetime
import os
import uuid
from pathlib import Path

import pytest
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models.functions import Now

from accounts.models import User
from core import recipes
from datasets.models import Dataset
from entities.models import Entity
from fitting.models import FittingResult
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
                    message='file',
                    contents='entity contents'):
        """Add a single commit/version to an entity"""
        entity.repo.create()
        in_repo_path = str(entity.repo_abs_path / filename)
        open(in_repo_path, 'w').write(contents)
        entity.repo.add_file(in_repo_path)
        commit = Helpers.fake_commit(entity.repo, message, User(full_name='author', email='author@example.com'))
        if tag_name:
            entity.repo.tag(tag_name)
        if visibility:
            entity.set_visibility_in_repo(commit, visibility)
        if cache:
            populate_entity_cache(entity)
        return commit

    @staticmethod
    def add_cached_version(entity, **kwargs):
        """
        Add a single commit/version to an entity along with a repocache entry.
        @return the relevant repocache entry
        """
        assert kwargs.get('cache', True), "Cache must be true for cached version"
        version = Helpers.add_version(entity, **kwargs)
        return entity.repocache.get_version(version.sha)

    @staticmethod
    def add_fake_version(entity, visibility='private', date=None, message='cache-only commit'):
        """Add a new commit/version only in the cache, not in git."""
        version = entity.repocache.CachedVersionClass.objects.create(
            entity=entity.repocache,
            sha=uuid.uuid4(),
            message=message,
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
    def link_to_protocol(protocol, *objects):
        """
        Link given objects to protocol (fitting specs or datasets)
        @param protocol - protocol to link to
        @param objects - list of objects to link to the protocol
        """
        for obj in objects:
            obj.protocol = protocol
            obj.save()


@pytest.fixture
def helpers():
    """
    Provide helpers in the form of a fixture
    """
    return Helpers


@pytest.fixture(autouse=True)
def fake_upload_path(settings, tmpdir):
    # Note that at present (Python 3.5, Django 1.11) Django requires this to be a string
    settings.MEDIA_ROOT = os.path.join(str(tmpdir), 'uploads')
    return settings.MEDIA_ROOT


@pytest.fixture(autouse=True)
def fake_experiment_path(settings, tmpdir):
    settings.EXPERIMENT_BASE = Path(str(tmpdir)) / 'experiments'
    return settings.EXPERIMENT_BASE


@pytest.fixture(autouse=True)
def fake_repo_path(settings, tmpdir):
    settings.REPO_BASE = Path(str(tmpdir)) / 'repos'
    return settings.REPO_BASE


@pytest.fixture(autouse=True)
def fake_dataset_path(settings, tmpdir):
    settings.DATASETS_BASE = Path(str(tmpdir)) / 'datasets'
    return settings.DATASETS_BASE


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
def fittingspec_with_version():
    fittingspec = recipes.fittingspec.make()
    Helpers.add_version(fittingspec, visibility='private')
    return fittingspec


@pytest.fixture
def public_model(helpers):
    model = recipes.model.make(name='public model')
    helpers.add_version(model, visibility='public')
    return model


@pytest.fixture
def public_protocol(helpers):
    protocol = recipes.protocol.make(name='public protocol')
    helpers.add_version(protocol, visibility='public')
    return protocol


@pytest.fixture
def public_fittingspec(helpers):
    fittingspec = recipes.fittingspec.make(name='public fitting spec')
    helpers.add_version(fittingspec, visibility='public')
    return fittingspec


@pytest.fixture
def public_dataset():
    dataset = recipes.dataset.make(visibility='public', name='public dataset')
    return dataset


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
def private_model(helpers):
    model = recipes.model.make(name='private model')
    helpers.add_version(model, visibility='private')
    return model


@pytest.fixture
def private_protocol(helpers):
    protocol = recipes.protocol.make(name='private protocol')
    helpers.add_version(protocol, visibility='private')
    return protocol


@pytest.fixture
def private_fittingspec(helpers):
    fittingspec = recipes.fittingspec.make(name='private fittingspec')
    helpers.add_version(fittingspec, visibility='private')
    return fittingspec


@pytest.fixture
def private_dataset():
    return recipes.dataset.make(visibility='private')


@pytest.fixture
def queued_experiment(model_with_version, protocol_with_version):
    version = recipes.experiment_version.make(
        status='QUEUED',
        experiment__model=model_with_version,
        experiment__model_version=model_with_version.repocache.latest_version,
        experiment__protocol=protocol_with_version,
        experiment__protocol_version=protocol_with_version.repocache.latest_version,
    )
    recipes.running_experiment.make(runnable=version)
    return version


@pytest.fixture
def experiment_with_result(model_with_version, protocol_with_version):
    version = recipes.experiment_version.make(
        status='SUCCESS',
        experiment__model=model_with_version,
        experiment__model_version=model_with_version.repocache.latest_version,
        experiment__protocol=protocol_with_version,
        experiment__protocol_version=protocol_with_version.repocache.latest_version,
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
        experiment__model_version=public_model.repocache.latest_version,
        experiment__protocol=public_protocol,
        experiment__protocol_version=public_protocol.repocache.latest_version,
    )


@pytest.fixture
def quick_experiment_version(helpers):
    """An experiment version that exists only in the DB - no model/proto repos, no results."""
    model = recipes.model.make()
    model_version = helpers.add_fake_version(model, 'public')
    protocol = recipes.protocol.make()
    protocol_version = helpers.add_fake_version(protocol, 'public')
    return recipes.experiment_version.make(
        status='SUCCESS',
        experiment__model=model,
        experiment__model_version=model_version,
        experiment__protocol=protocol,
        experiment__protocol_version=protocol_version,
    )


@pytest.fixture
def moderated_experiment_version(moderated_model, moderated_protocol):
    return recipes.experiment_version.make(
        status='SUCCESS',
        experiment__model=moderated_model,
        experiment__model_version=moderated_model.repocache.latest_version,
        experiment__protocol=moderated_protocol,
        experiment__protocol_version=moderated_protocol.repocache.latest_version,
    )


@pytest.fixture
def admin_user():
    user = User.objects.create_superuser(
        email='admin@example.com',
        full_name='Admin User',
        institution='UCL',
        password='password',
    )
    yield user


@pytest.fixture
def user():
    user = User.objects.create_user(
        email='test@example.com',
        full_name='Test User',
        institution='UCL',
        password='password',
    )
    yield user


@pytest.fixture
def other_user():
    user = User.objects.create_user(
        email='other@example.com',
        full_name='Other User',
        institution='UCL',
        password='password',
    )
    yield user


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
def fits_user(logged_in_user):
    content_type = ContentType.objects.get_for_model(FittingResult)
    permission = Permission.objects.get(
        codename='run_fits',
        content_type=content_type,
    )
    logged_in_user.user_permissions.add(permission)
    return logged_in_user


@pytest.fixture
def dataset_creator(user, helpers):
    helpers.add_permission(user, 'create_dataset', Dataset)
    return user


@pytest.fixture
def my_dataset(logged_in_user, helpers, public_protocol):
    helpers.add_permission(logged_in_user, 'create_dataset', Dataset)
    dataset = recipes.dataset.make(author=logged_in_user, name='mydataset', protocol=public_protocol)
    yield dataset
    dataset.delete()


@pytest.fixture
def my_dataset_with_file(logged_in_user, helpers, public_protocol, client):
    helpers.add_permission(logged_in_user, 'create_dataset', Dataset)
    dataset = recipes.dataset.make(author=logged_in_user, name='mydataset', protocol=public_protocol)
    file_name = 'mydataset.csv'
    file_contents = b'my test dataset'
    recipes.dataset_file.make(
        dataset=dataset,
        upload=SimpleUploadedFile(file_name, file_contents),
        original_name=file_name,
    )
    client.post(
        '/datasets/%d/addfiles' % dataset.pk,
        data={
            'filename[]': ['uploads/' + file_name],
            'delete_filename[]': [],
            'mainEntry': [file_name],
        },
    )
    yield dataset
    dataset.delete()


@pytest.fixture
def fittingresult_version(public_model, public_protocol, public_fittingspec, public_dataset):
    return recipes.fittingresult_version.make(
        status='SUCCESS',
        fittingresult__model=public_model,
        fittingresult__model_version=public_model.repocache.latest_version,
        fittingresult__protocol=public_protocol,
        fittingresult__protocol_version=public_protocol.repocache.latest_version,
        fittingresult__fittingspec=public_fittingspec,
        fittingresult__fittingspec_version=public_fittingspec.repocache.latest_version,
        fittingresult__dataset=public_dataset,
    )


@pytest.fixture
def fittingresult_with_result(model_with_version, protocol_with_version):
    version = recipes.fittingresult_version.make(
        status='SUCCESS',
        fittingresult__model=model_with_version,
        fittingresult__model_version=model_with_version.repocache.latest_version,
        fittingresult__protocol=protocol_with_version,
        fittingresult__protocol_version=protocol_with_version.repocache.latest_version,
    )
    version.mkdir()
    with (version.abs_path / 'result.txt').open('w') as f:
        f.write('fitting results')
    return version
