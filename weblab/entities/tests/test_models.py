import pytest
from django.db.utils import IntegrityError

from core import recipes
from entities.models import ModelEntity, ProtocolEntity
from repocache.exceptions import RepoCacheMiss
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

    def test_get_and_set_visibility_in_repo(self, helpers):
        model = recipes.model.make()
        commit = helpers.add_version(model, cache=False)
        assert model.get_visibility_from_repo(commit) is None

        model.set_visibility_in_repo(commit, 'restricted')
        assert model.get_visibility_from_repo(commit) == 'restricted'
        assert commit.get_note() == 'Visibility: restricted'

    def test_get_repocache(self):
        model = recipes.model.make()
        assert CachedEntity.objects.count() == 0
        assert model.repocache
        assert CachedEntity.objects.count() == 1
        assert model.repocache
        assert CachedEntity.objects.count() == 1

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

    def test_set_version_visibility_updates_cache(self, helpers):
        model = recipes.model.make()
        sha = helpers.add_version(model).hexsha

        populate_entity_cache(model)

        model.set_version_visibility(sha, 'restricted')

        assert model.cachedentity.versions.get().visibility == 'restricted'

    def test_get_ref_version_visibility(self, helpers):
        model = recipes.model.make()
        sha = helpers.add_version(model, visibility='restricted').hexsha
        model.add_tag('v1', sha)

        assert model.get_ref_version_visibility(sha) == 'restricted'
        assert model.get_ref_version_visibility('v1') == 'restricted'
        assert model.get_ref_version_visibility('latest') == 'restricted'

    def test_get_ref_version_visibility_invalid_hexsha(self, helpers):
        model = recipes.model.make()
        sha = helpers.add_version(model, visibility='restricted').hexsha

        with pytest.raises(RepoCacheMiss):
            model.get_ref_version_visibility('0'*40)

    def test_get_ref_version_visibility_invalid_tag(self, helpers):
        model = recipes.model.make()
        sha = helpers.add_version(model, visibility='restricted').hexsha

        with pytest.raises(RepoCacheMiss):
            model.get_ref_version_visibility('v10')

    def test_add_tag(self, helpers):
        model = recipes.model.make()
        sha = helpers.add_version(model).hexsha
        populate_entity_cache(model)

        model.add_tag('mytag', sha)

        assert model.cachedentity.tags.get().tag == 'mytag'
        assert model.repo.tag_dict[sha][0].name == 'mytag'

        assert model.get_tags(sha) == {'mytag'}
