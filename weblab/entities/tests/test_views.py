import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from entities.models import EntityUpload, ModelEntity, ProtocolEntity


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


@pytest.fixture(autouse=True)
def fake_repo_path(settings, tmpdir):
    settings.REPO_BASE = str(tmpdir)
    yield settings.REPO_BASE


@pytest.fixture(autouse=True)
def fake_upload_path(settings, tmpdir):
    settings.MEDIA_ROOT = str(tmpdir)
    yield settings.MEDIA_ROOT


@pytest.mark.django_db
def test_create_model(user, client, fake_repo_path):
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


@pytest.mark.django_db
def test_create_protocol(user, client):
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


@pytest.mark.django_db
def test_create_model_version(user, client):
    model = ModelEntity.objects.create(
        name='mymodel',
        visibility='public',
        author=user,
    )
    EntityUpload.objects.create(
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


@pytest.mark.django_db
def test_create_protocol_version(user, client):
    protocol = ProtocolEntity.objects.create(
        name='myprotocol',
        visibility='public',
        author=user,
    )
    EntityUpload.objects.create(
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
