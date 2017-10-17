import os.path

import pytest

from accounts.models import User
from entities.models import ModelEntity, ProtocolEntity


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
def fake_repo_path(settings, tmpdir):
    settings.REPO_BASE = str(tmpdir)
    yield tmpdir


@pytest.mark.django_db
def test_create_model(user, client, fake_repo_path):
    response = client.post('/entities/models/new', data={
        'name': 'mymodel',
        'visibility': 'private',
    })
    assert response.status_code == 302

    assert ModelEntity.objects.count() == 1

    entity = ModelEntity.objects.first()
    assert entity.name == 'mymodel'
    assert entity.visibility == 'private'
    assert entity.author == user

    assert entity.repo_abs_path.exists()


@pytest.mark.django_db
def test_create_protocol(user, client, fake_repo_path):
    response = client.post('/entities/protocols/new', data={
        'name': 'myprotocol',
        'visibility': 'public',
    })
    assert response.status_code == 302

    assert ProtocolEntity.objects.count() == 1

    entity = ProtocolEntity.objects.first()
    assert entity.name == 'myprotocol'
    assert entity.visibility == 'public'
    assert entity.author == user

    assert entity.repo_abs_path.exists()


@pytest.mark.skip
def test_create_model_version(user, client, fake_repo_path):
    proto = ProtocolEntity.objects.create(
        name='myprotocol',
        visibility='public',
        author=user,
    )
    response = client.post(
        '/entities/protocols/' + proto.pk + '/versions/new',
        data={
        },
    )

