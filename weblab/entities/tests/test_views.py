import os.path
import shutil

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
    assert entity.author.email == 'test@example.com'

    assert os.path.exists(fake_repo_path + str(user.id) + '/models/mymodel')

@pytest.fixture
def fake_repo_path(settings):
    settings.REPO_BASE = '/tmp/repos/'

    yield settings.REPO_BASE

    shutil.rmtree(settings.REPO_BASE)


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
    assert entity.author.email == 'test@example.com'

    assert os.path.exists(fake_repo_path + str(user.id) + '/protocols/myprotocol')
