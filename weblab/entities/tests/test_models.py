import pytest
from django.db.utils import IntegrityError

from core import recipes
from entities.models import ModelEntity, ProtocolEntity


@pytest.mark.django_db
class TestEntityNameUniqueness:
    def test_user_cannot_have_same_named_model(self):
        user = recipes.user.make()
        recipes.model.make(author=user, name='mymodel')

        with pytest.raises(IntegrityError):
            ModelEntity.objects.create(author=user, name='mymodel')

    def test_user_can_have_same_named_model_and_protocol(self):
        user = recipes.user.make()
        ModelEntity.objects.create(author=user, name='myentity')
        ProtocolEntity.objects.create(author=user, name='myentity')

    def test_different_users_can_have_same_named_model(self):
        user, other_user = recipes.user.make(_quantity=2)
        ModelEntity.objects.create(author=user, name='mymodel')
        assert ModelEntity.objects.create(author=other_user, name='mymodel')


@pytest.mark.django_db
def test_deletion():
    user, other_user = recipes.user.make(_quantity=2)
    model = recipes.model.make(author=user)
    superuser = recipes.user.make(is_superuser=True)

    assert model.is_deletable_by(user)
    assert model.is_deletable_by(superuser)
    assert not model.is_deletable_by(other_user)


@pytest.mark.django_db
class TestEntityManager:
    def test_visible_to_user(self):
        user, other_user = recipes.user.make(_quantity=2)
        mine = recipes.model.make(author=user)
        other_restricted = recipes.model.make(author=other_user, visibility='restricted')

        # should not be visible
        recipes.model.make(author=other_user, visibility='private')

        assert list(ModelEntity.objects.visible_to_user(user)) == [
            mine, other_restricted
        ]
