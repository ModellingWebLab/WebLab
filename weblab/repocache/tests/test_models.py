import pytest
from django.db.utils import IntegrityError

from core import recipes
from repocache.models import CachedModel, CachedProtocol


@pytest.mark.django_db
class TestEntityCacheModels:
    @pytest.mark.parametrize("recipe,manager", [
        (recipes.cached_model, CachedModel.objects),
        (recipes.cached_protocol, CachedProtocol.objects),
    ])
    def test_cachedentity_is_deleted_when_entity_is_deleted(self, recipe, manager):
        cached = recipe.make()
        cached.entity.delete()
        assert not manager.filter(pk=cached.pk).exists()

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_version),
        (recipes.cached_protocol_version),
    ])
    def test_related_names_for_versions(self, recipe):
        version = recipe.make()
        assert list(version.entity.versions.all()) == [version]

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_tag),
        (recipes.cached_protocol_tag),
    ])
    def test_related_names_for_tags(self, recipe):
        tag = recipe.make()
        assert list(tag.entity.tags.all()) == [tag]

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_version),
        (recipes.cached_protocol_version),
    ])
    def test_uniqueness_of_entity_and_version_sha(self, recipe):
        version = recipe.make()
        with pytest.raises(IntegrityError):
            recipe.make(entity=version.entity, sha=version.sha)

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_tag),
        (recipes.cached_protocol_tag),
    ])
    def test_uniqueness_of_entity_and_tag(self, recipe):
        version = recipe.make()
        with pytest.raises(IntegrityError):
            recipe.make(entity=version.entity, tag=version.tag)

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model),
        (recipes.cached_protocol),
    ])
    def test_uniqueness_of_entity(self, recipe):
        cached = recipe.make()
        with pytest.raises(IntegrityError):
            recipe.make(entity=cached.entity)


@pytest.mark.django_db
class TestEntityCacheModelsVisibility:
    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_version),
        (recipes.cached_protocol_version),
    ])
    def test_entity_visibility(self, recipe):
        version = recipe.make(visibility='public')
        assert version.entity.visibility == 'public'

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model),
        (recipes.cached_protocol),
    ])
    def test_entity_visibility_is_private_if_no_versions(self, recipe):
        cached = recipe.make()
        assert cached.visibility == 'private'

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_version),
        (recipes.cached_protocol_version),
    ])
    def test_get_version(self, recipe):
        version = recipe.make()
        assert version.entity.get_version(version.sha) == version

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_version),
        (recipes.cached_protocol_version),
    ])
    def test_set_entity_version_visibility(self, recipe):
        version = recipe.make()
        version.set_visibility('public')
        version.refresh_from_db()
        assert version.visibility == 'public'

    def test_add_version(self, helpers):
        model = recipes.model.make()
        commit = helpers.add_version(model, visibility='public', cache=False)

        assert model.repocache.versions.count() == 0
        model.repocache.add_version(commit.sha)

        version = model.repocache.get_version(commit.sha)
        assert version.sha == commit.sha
        assert version.message == commit.message
        assert version.master_filename == commit.master_filename
        assert version.timestamp == commit.timestamp
        assert version.author == commit.author.name
        assert version.numfiles == len(commit.filenames)
        assert version.visibility == 'public'
