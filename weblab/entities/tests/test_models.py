import pytest
from django.db.utils import IntegrityError

from core import recipes
from entities.models import ModelEntity, ProtocolEntity
from repocache.models import CachedEntity
from repocache.populate import populate_entity_cache


@pytest.mark.django_db
class TestEntityNameUniqueness:
    def test_user_cannot_have_same_named_model(self, user):
        recipes.model.make(author=user, name='mymodel')

        with pytest.raises(IntegrityError):
            ModelEntity.objects.create(author=user, name='mymodel')

    def test_user_can_have_same_named_model_and_protocol(self, user):
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
class TestEntity:
    def test_str(self):
        model = recipes.model.make(name='test model')
        assert str(model) == 'test model'

    def test_repo_abs_path(self, fake_repo_path):
        model = recipes.model.make()
        path = '%s/%d/models/%d' % (fake_repo_path, model.author.pk, model.pk)

        assert model.repo._root == path
        assert str(model.repo_abs_path) == path

    def test_nice_version(self, model_with_version):
        commit = model_with_version.repo.latest_commit.hexsha
        assert model_with_version.nice_version(commit) == '%s...' % commit[:8]

        model_with_version.repo.tag('v1')
        assert model_with_version.nice_version(commit) == 'v1'

    def test_set_and_get_version_visibility(self, model_with_version):
        commit = model_with_version.repo.latest_commit
        model_with_version.set_version_visibility(commit.hexsha, 'restricted')

        assert model_with_version.get_version_visibility(commit.hexsha) == 'restricted'

    def test_version_visibility_ignores_invalid_format(self, model_with_version):
        commit = model_with_version.repo.latest_commit
        commit.add_note('invalid note format')
        CachedEntity.objects.all().delete()

        # falls back to private visibility
        assert model_with_version.get_version_visibility(commit.hexsha) == 'private'

    def test_entity_visibility_gets_latest_visibility_from_cache(self):
        model = recipes.model.make()
        recipes.cached_entity_version.make(
            entity__entity=model,
            sha='test-sha',
            visibility='restricted'
        )

        assert model.visibility == 'restricted'

    def test_get_version_visibility_fetches_from_cache(self):
        model = recipes.model.make()
        recipes.cached_entity_version.make(
            entity__entity=model,
            sha='test-sha',
            visibility='restricted'
        )

        assert model.get_version_visibility('test-sha') == 'restricted'

    def test_set_version_visibility_updates_cache(self, model_with_version):
        model = model_with_version
        populate_entity_cache(model)

        model.set_version_visibility('latest', 'restricted')

        assert model.cachedentity.versions.get().visibility == 'restricted'
