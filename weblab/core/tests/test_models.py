import pytest

from core import recipes


@pytest.mark.django_db
class TestUserCreatedModelMixin:
    def test_is_deletable_by(self, user, admin_user, other_user):
        model = recipes.model.make(author=user)
        assert model.is_deletable_by(user)
        assert model.is_deletable_by(admin_user)
        assert not model.is_deletable_by(other_user)

    def test_visibility_editable_by(self, user, admin_user, other_user):
        model = recipes.model.make(author=user)
        assert model.is_visibility_editable_by(user)
        assert model.is_visibility_editable_by(admin_user)
        assert not model.is_visibility_editable_by(other_user)
