import pytest
from guardian.shortcuts import assign_perm

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

    def test_admin_can_edit_any_entity(self, admin_user):
        model = recipes.model.make()
        assert model.is_editable_by(admin_user)

    def test_can_edit_own_entity_with_global_permission(self, user, helpers):
        model = recipes.model.make(author=user)
        helpers.add_permission(user, 'create_model')
        user = User.objects.get(pk=user.pk)
        assert model.is_editable_by(user)

    def test_cannot_edit_own_entity_without_global_permission(self, user):
        # User doesn't have entity creation permissions, so they can't
        # create a new version even on their own entity
        model = recipes.model.make(author=user)
        assert not model.is_editable_by(user)

    def test_cannot_edit_somebody_elses_entity(self, user, helpers):
        # Even with the right permissions, another user shouldn't be able to edit entity
        model = recipes.model.make()
        helpers.add_permission(user, 'create_model')
        assert not model.is_editable_by(user)

    def test_can_edit_somebody_elses_entity_with_object_permission(self, user, other_user, helpers):
        model = recipes.model.make()
        helpers.add_permission(user, 'create_model')
        assign_perm('edit_entity', user, model)
        assert model.is_editable_by(user)
