import pytest
from django.db.utils import IntegrityError
from django.shortcuts import get_object_or_404
from guardian.shortcuts import assign_perm

from core import recipes
from repocache.models import CachedFittingSpec


@pytest.mark.django_db
class TestNameUniqueness:
    def test_user_cannot_have_same_named_fittingspec(self, user):
        spec = recipes.fittingspec.make(author=user, name='myspec')
        assert str(spec) == 'myspec'

        with pytest.raises(IntegrityError):
            recipes.fittingspec.make(author=user, name='myspec')

    def test_user_can_have_same_named_fittingspec_and_other_entities(self, user):
        recipes.fittingspec.make(author=user, name='myentity')
        recipes.model.make(author=user, name='myentity')
        recipes.protocol.make(author=user, name='myentity')

    def test_different_users_can_have_same_named_fittingspec(self, user, other_user):
        recipes.fittingspec.make(author=user, name='myspec')
        assert recipes.fittingspec.make(author=other_user, name='myspec')


@pytest.mark.django_db
def test_permissions():
    user, other_user = recipes.user.make(_quantity=2)
    superuser = recipes.user.make(is_superuser=True)
    fittingspec = recipes.fittingspec.make(author=user)

    assert fittingspec.viewers == {user}

    assert not fittingspec.is_editable_by(user)
    assert fittingspec.is_editable_by(superuser)
    assert not fittingspec.is_editable_by(other_user)

    assign_perm('entities.create_fittingspec', user)
    user = get_object_or_404(user.__class__, pk=user.id)  # Reset permission cache!
    assert fittingspec.is_editable_by(user)

    assert fittingspec.is_deletable_by(user)
    assert fittingspec.is_deletable_by(superuser)
    assert not fittingspec.is_deletable_by(other_user)

    fittingspec.add_collaborator(other_user)
    assert other_user in fittingspec.collaborators
    assert fittingspec.viewers == {user, other_user}
    assert not fittingspec.is_editable_by(other_user)
    assert not fittingspec.is_deletable_by(other_user)

    assign_perm('entities.create_fittingspec', other_user)
    other_user = get_object_or_404(user.__class__, pk=other_user.id)  # Reset permission cache!
    assert fittingspec.is_editable_by(other_user)

    fittingspec.remove_collaborator(other_user)
    assert other_user not in fittingspec.collaborators
    assert not fittingspec.is_editable_by(other_user)
    assert not fittingspec.is_deletable_by(other_user)


@pytest.mark.django_db
class TestRepository:
    def test_repo_path_create_and_delete(self, fake_repo_path):
        spec = recipes.fittingspec.make()
        path = '%s/%d/fittingspecs/%d' % (fake_repo_path, spec.author.pk, spec.pk)

        assert spec.repo._root == path
        assert str(spec.repo_abs_path) == path

    def test_repo_is_deleted(self):
        spec = recipes.fittingspec.make()
        spec.repo.create()
        assert spec.repo_abs_path.exists()
        spec.delete()
        assert not spec.repo_abs_path.exists()

    def test_get_repocache(self):
        spec = recipes.fittingspec.make()
        assert CachedFittingSpec.objects.count() == 0
        assert spec.repocache
        assert CachedFittingSpec.objects.count() == 1
        assert spec.repocache
        assert CachedFittingSpec.objects.count() == 1
        spec.delete()
        assert CachedFittingSpec.objects.count() == 0
