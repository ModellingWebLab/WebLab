import io
import json

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from entities.models import Entity, EntityFile, ModelEntity, ProtocolEntity


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
class TestVersionCreation:
    def test_create_model_version(self, user, client):
        add_permission(user, 'create_model_version')
        model = ModelEntity.objects.create(
            name='mymodel',
            visibility='public',
            author=user,
        )
        EntityFile.objects.create(
            entity=model,
            upload=SimpleUploadedFile('model.txt', b'my test model'),
            original_name='model.txt',
        )
        response = client.post(
            '/entities/models/' + str(model.pk) + '/versions/new',
            data={
                'filename[]': 'uploads/model.txt',
                'commit_message': 'first commit',
                'version': 'v1',
            },
        )
        assert response.status_code == 302
        assert response.url == '/entities/models/%d' % model.id
        assert 'v1' in model.repo.tags
        assert model.repo.head.commit.message == 'first commit'
        assert model.repo.head.commit.tree.blobs[0].name == 'model.txt'

    def test_create_model_version_requires_permissions(self, user, client):
        model = ModelEntity.objects.create(
            name='mymodel',
            visibility='public',
            author=user,
        )
        response = client.post(
            '/entities/models/' + str(model.pk) + '/versions/new',
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_create_protocol_version(self, user, client):
        add_permission(user, 'create_protocol_version')
        protocol = ProtocolEntity.objects.create(
            name='myprotocol',
            visibility='public',
            author=user,
        )
        EntityFile.objects.create(
            entity=protocol,
            upload=SimpleUploadedFile('protocol.txt', b'my test protocol'),
            original_name='protocol.txt',
        )
        response = client.post(
            '/entities/protocols/' + str(protocol.pk) + '/versions/new',
            data={
                'filename[]': 'uploads/protocol.txt',
                'commit_message': 'first commit',
                'version': 'v1',
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
        model = ProtocolEntity.objects.create(
            name='myprotocol',
            visibility='public',
            author=user,
        )
        response = client.post(
            '/entities/protocols/' + str(model.pk) + '/versions/new',
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url


@pytest.mark.django_db
def test_upload_file(user, client):
    model = ModelEntity.objects.create(
        name='mymodel',
        visibility='public',
        author=user,
    )

    upload = io.StringIO('my test model')
    upload.name = 'model.txt'
    response = client.post(
        '/entities/' + str(model.pk) + '/upload-file',
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
