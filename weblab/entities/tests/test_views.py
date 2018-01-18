import io
import json

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from core import recipes
from entities.models import Entity, ModelEntity, ProtocolEntity


@pytest.fixture
def user(client):
    user = User.objects.create_user(
        email='test@example.com',
        full_name='Test User',
        institution='UCL',
        password='password',
    )
    client.login(username='test@example.com', password='password')
    return user


@pytest.fixture
def other_user():
    return recipes.user.make()


def add_permission(user, perm):
    content_type = ContentType.objects.get_for_model(Entity)
    permission = Permission.objects.get(
        codename=perm,
        content_type=content_type,
    )
    user.user_permissions.add(permission)


@pytest.fixture(autouse=True)
def fake_repo_path(settings, tmpdir):
    settings.REPO_BASE = str(tmpdir)
    return settings.REPO_BASE


@pytest.fixture(autouse=True)
def fake_upload_path(settings, tmpdir):
    settings.MEDIA_ROOT = str(tmpdir)
    return settings.MEDIA_ROOT


def add_version(entity):
    """Add a single commit/version to an entity"""
    entity.init_repo()
    in_repo_path = str(entity.repo_abs_path / 'entity.txt')
    open(in_repo_path, 'w').write('entity contents')
    entity.add_file_to_repo(in_repo_path)
    entity.commit_repo('file', 'author', 'author@example.com')


@pytest.mark.django_db
class TestEntityCreation:
    def test_create_model(self, user, client, fake_repo_path):
        add_permission(user, 'create_model')
        response = client.post('/entities/models/new', data={
            'name': 'mymodel',
            'visibility': 'private',
        })
        assert response.status_code == 302

        assert ModelEntity.objects.count() == 1

        entity = ModelEntity.objects.first()
        assert response.url == '/entities/models/%d/versions/new' % entity.id
        assert entity.name == 'mymodel'
        assert entity.visibility == 'private'
        assert entity.author == user

        assert entity.repo_abs_path.exists()

    def test_create_model_requires_permissions(self, user, client):
        response = client.post(
            '/entities/models/new',
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_create_protocol(self, user, client):
        add_permission(user, 'create_protocol')
        response = client.post('/entities/protocols/new', data={
            'name': 'myprotocol',
            'visibility': 'public',
        })
        assert response.status_code == 302

        assert ProtocolEntity.objects.count() == 1

        entity = ProtocolEntity.objects.first()
        assert response.url == '/entities/protocols/%d/versions/new' % entity.id
        assert entity.name == 'myprotocol'
        assert entity.visibility == 'public'
        assert entity.author == user

        assert entity.repo_abs_path.exists()

    def test_create_protocol_requires_permissions(self, user, client):
        response = client.post(
            '/entities/protocols/new',
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url


@pytest.mark.django_db
class TestEntityDetail:
    def test_redirects_to_latest_version(self, client, user):
        model = recipes.model.make()
        add_version(model)
        response = client.get('/entities/models/%d' % model.pk)
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/latest' % model.pk


@pytest.mark.django_db
class TestEntityVersionDetail:
    def check(self, client, url, version, tag):
        response = client.get(url)
        assert response.status_code == 200
        assert response.context['version'] == version
        if tag:
            assert response.context['tag'].name == tag
        else:
            assert response.context['tag'] is None

    def test_view_entity_version(self, client, user):
        model = recipes.model.make()
        add_version(model)
        commit = next(model.commits)
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, commit.hexsha),
                   commit, None)
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   commit, None)

        # Now add a second version with tag
        assert len(list(model.commits)) == 1
        add_version(model)
        model.tag_repo('my_tag')

        # Commits are yielded newest first
        assert len(list(model.commits)) == 2
        assert commit == list(model.commits)[-1]
        commit = next(model.commits)

        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, commit.hexsha),
                   commit, 'my_tag')
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, 'my_tag'),
                   commit, 'my_tag')
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   commit, 'my_tag')


@pytest.mark.django_db
class TestEntityVersionList:
    def test_view_entity_version_list(self, client, user):
        model = recipes.model.make()
        add_version(model)

        response = client.get('/entities/models/%d/versions/' % model.pk)
        assert response.status_code == 200
        assert response.context['versions'] == [(None, next(model.commits))]


@pytest.mark.django_db
class TestEntityList:
    def test_lists_my_models(self, client, user):
        models = recipes.model.make(_quantity=2, author=user)
        response = client.get('/entities/models/')
        assert response.status_code == 200
        assert list(response.context['object_list']) == models

    def test_lists_my_protocols(self, client, user):
        protocols = recipes.protocol.make(_quantity=2, author=user)
        response = client.get('/entities/protocols/')
        assert response.status_code == 200
        assert list(response.context['object_list']) == protocols


@pytest.mark.django_db
class TestVersionCreation:
    def test_new_version_form_includes_latest_version(self, client, user):
        model = recipes.model.make()
        add_version(model)
        add_permission(user, 'create_model_version')
        commit = next(model.commits)
        response = client.get('/entities/models/%d/versions/new' % model.pk)
        assert response.status_code == 200
        assert response.context['latest_version'] == commit

    def test_no_latest_version(self, client, user):
        add_permission(user, 'create_model_version')
        model = recipes.model.make()
        response = client.get('/entities/models/%d/versions/new' % model.pk)
        assert response.status_code == 200
        assert 'latest_version' not in response.context

    def test_create_model_version(self, user, client):
        add_permission(user, 'create_model_version')
        model = recipes.model_file.make(
            entity__author=user,
            upload=SimpleUploadedFile('model.txt', b'my test model'),
            original_name='model.txt',
        ).entity
        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'filename[]': 'uploads/model.txt',
                'commit_message': 'first commit',
                'tag': 'v1',
            },
        )
        assert response.status_code == 302
        assert response.url == '/entities/models/%d' % model.id
        assert 'v1' in model.repo.tags
        assert model.repo.head.commit.message == 'first commit'
        assert model.repo.head.commit.tree.blobs[0].name == 'model.txt'

    def test_create_model_version_requires_permissions(self, user, client):
        model = recipes.model.make(author=user)
        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_create_protocol_version(self, user, client):
        add_permission(user, 'create_protocol_version')
        protocol = recipes.protocol_file.make(
            entity__author=user,
            upload=SimpleUploadedFile('protocol.txt', b'my test protocol'),
            original_name='protocol.txt',
        ).entity
        response = client.post(
            '/entities/protocols/%d/versions/new' % protocol.pk,
            data={
                'filename[]': 'uploads/protocol.txt',
                'commit_message': 'first commit',
                'tag': 'v1',
            },
        )
        assert response.status_code == 302
        assert response.url == '/entities/protocols/%d' % protocol.id
        assert 'v1' in protocol.repo.tags
        assert protocol.repo.head.commit.message == 'first commit'
        assert protocol.repo.head.commit.tree.blobs[0].name == 'protocol.txt'
        assert protocol.repo.head.commit.author.email == user.email
        assert protocol.repo.head.commit.author.name == user.full_name

    def test_create_protocol_version_requires_permissions(self, user, client):
        protocol = recipes.protocol.make(author=user)
        response = client.post(
            '/entities/protocols/%d/versions/new' % protocol.pk,
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url


@pytest.mark.django_db
class TestFileUpload:
    def test_upload_file(self, user, client):
        model = recipes.model.make(author=user)

        upload = io.StringIO('my test model')
        upload.name = 'model.txt'
        response = client.post(
            '/entities/%d/upload-file' % model.pk,
            {
                'upload': upload
            }
        )

        data = json.loads(response.content.decode())
        upload = data['files'][0]
        assert upload['stored_name'] == 'uploads/model.txt'
        assert upload['name'] == 'model.txt'
        assert upload['is_valid']
        assert upload['size'] == 13

        assert model.files.count() == 1

    def test_bad_upload(self, user, client):
        model = recipes.model.make(author=user)

        response = client.post('/entities/%d/upload-file' % model.pk, {})

        assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("recipe,url", [
    (recipes.model, '/entities/models/%d'),
    (recipes.model, '/entities/models/%d/versions/'),
    (recipes.model, '/entities/models/%d/versions/latest'),
    (recipes.protocol, '/entities/protocols/%d'),
    (recipes.protocol, '/entities/protocols/%d/versions/'),
    (recipes.protocol, '/entities/protocols/%d/versions/latest'),
])
class TestEntityVisibility:
    def test_private_entity_visible_to_self(self, client, user, recipe, url):
        entity = recipe.make(visibility='private', author=user)
        add_version(entity)
        assert client.get(url % entity.pk, follow=True).status_code == 200

    def test_private_entity_invisible_to_other_user(self, client, user, other_user, recipe, url):
        entity = recipe.make(visibility='private', author=other_user)
        add_version(entity)
        response = client.get(url % entity.pk)
        assert response.status_code == 404

    def test_private_entity_requires_login_for_anonymous(self, client, recipe, url):
        entity = recipe.make(visibility='private')
        add_version(entity)
        response = client.get(url % entity.pk)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_restricted_entity_visible_to_other_user(self, client, user, other_user, recipe, url):
        entity = recipe.make(visibility='restricted', author=other_user)
        add_version(entity)
        assert client.get(url % entity.pk, follow=True).status_code == 200

    def test_restricted_entity_requires_login_for_anonymous(self, client, recipe, url):
        entity = recipe.make(visibility='restricted')
        add_version(entity)
        response = client.get(url % entity.pk)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_public_entity_visible_to_anonymous(self, client, recipe, url):
        entity = recipe.make(visibility='public')
        add_version(entity)
        assert client.get(url % entity.pk, follow=True).status_code == 200

    def test_nonexistent_entity_redirects_anonymous_to_login(self, client, recipe, url):
        response = client.get(url % 10000)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_nonexistent_entity_generates_404_for_user(self, client, user, recipe, url):
        response = client.get(url % 10000)
        assert response.status_code == 404
