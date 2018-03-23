import json

import pytest

from accounts.models import User
from core import recipes


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
class TestExperimentMatrix:
    def test_matrix(self, client, user):
        model = recipes.model.make()
        protocol = recipes.protocol.make()
        exp = recipes.experiment.make(model=model, protocol=protocol)

        response = client.get('/experiments/matrix')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert str(model.pk) in data['getMatrix']['models']
        assert str(protocol.pk) in data['getMatrix']['protocols']
        assert str(exp.pk) in data['getMatrix']['experiments']
