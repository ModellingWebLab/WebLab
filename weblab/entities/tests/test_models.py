import pytest
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError

from accounts.models import User
from entities.models import ModelEntity, ProtocolEntity


@pytest.fixture
def user(client):
    return User.objects.create_user(
        email='test@example.com',
        full_name='Test User',
        institution='UCL',
    )


@pytest.mark.django_db
class TestEntityNameUniqueness:
    def test_user_cannot_have_same_named_model(self, user):
        ModelEntity.objects.create(author=user, name='mymodel')

        with pytest.raises(IntegrityError):
            ModelEntity.objects.create(author=user, name='mymodel')

    def test_user_can_have_same_named_model_and_protocol(self, user):
        ModelEntity.objects.create(author=user, name='myentity')
        ProtocolEntity.objects.create(author=user, name='myentity')

    def test_different_users_can_have_same_named_model(self, user):
        other = User.objects.create(
            email='other@example.com',
            full_name='Other User',
            institution='UCL',
        )
        ModelEntity.objects.create(author=user, name='mymodel')
        assert ModelEntity.objects.create(author=other, name='mymodel')
