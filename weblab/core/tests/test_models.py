import pytest
from core import recipes
from guardian.shortcuts import assign_perm


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

    def test_can_edit_own_entity_with_global_permission(self, user):
        model = recipes.model.make(author=user)
        assign_perm('entities.create_model', user)
        assert model.is_editable_by(user)

    def test_cannot_edit_own_entity_without_global_permission(self, user):
        # User doesn't have entity creation permissions, so they can't
        # create a new version even on their own entity
        model = recipes.model.make(author=user)
        assert not model.is_editable_by(user)

    def test_cannot_edit_somebody_elses_entity(self, user):
        # Even with the right permissions, another user shouldn't be able to edit entity
        model = recipes.model.make()
        assign_perm('entities.create_model', user)
        assert not model.is_editable_by(user)

    def test_can_edit_somebody_elses_entity_with_object_permission(self, user):
        model = recipes.model.make()
        assign_perm('entities.create_model', user)
        assign_perm('edit_entity', user, model)
        assert model.is_editable_by(user)

    def test_is_collaborator_if_has_edit_permission(self, user):
        model = recipes.model.make()
        assert user not in model.collaborators

        assign_perm('edit_entity', user, model)
        assert user in model.collaborators

    def test_is_viewer_if_has_edit_permission(self, user):
        model = recipes.model.make()
        assign_perm('edit_entity', user, model)
        assert user in model.viewers

    def test_is_viewer_if_is_author(self, user):
        model = recipes.model.make(author=user)
        assert model.viewers == {user}
