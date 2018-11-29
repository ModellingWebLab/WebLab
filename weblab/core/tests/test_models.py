import pytest

from accounts.models import User
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

    def test_editable_by_admin(self, admin_user):
        model = recipes.model.make()
        assert model.is_editable_by(admin_user)

    def test_editable_by_user_with_permissions(self, user, helpers):
        model = recipes.model.make(author=user)
        helpers.add_permission(user, 'create_model')
        user = User.objects.get(pk=user.pk)
        assert model.is_editable_by(user)

    def test_not_editable_by_user_without_permissions(self, user):
        # User doesn't have entity creation permissions, so they can't
        # create a new version even on their own entity
        model = recipes.model.make(author=user)
        assert not model.is_editable_by(user)

    def test_not_editable_by_user_without_permissions(self, user, other_user, helpers):
        # Even with the right permissions, another user shouldn't be able to edit entity
        model = recipes.model.make(author=user)
        helpers.add_permission(other_user, 'create_model')
        assert not model.is_editable_by(other_user)
