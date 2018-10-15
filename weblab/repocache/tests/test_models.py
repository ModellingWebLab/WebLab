import pytest
from django.db.utils import IntegrityError

from core import recipes


@pytest.mark.django_db
class TestEntityCacheModels:
    def test_related_names_for_versions(self):
        version = recipes.cached_entity_version.make()
        assert list(version.entity.versions.all()) == [version]

    def test_related_names_for_tags(self):
        tag = recipes.cached_entity_tag.make()
        assert list(tag.entity.tags.all()) == [tag]

    def test_uniqueness_of_entity_and_version_sha(self):
        version = recipes.cached_entity_version.make()
        with pytest.raises(IntegrityError):
            recipes.cached_entity_version.make(entity=version.entity, sha=version.sha)

    def test_uniqueness_of_entity_and_tag(self):
        version = recipes.cached_entity_tag.make()
        with pytest.raises(IntegrityError):
            recipes.cached_entity_tag.make(entity=version.entity, tag=version.tag)

    def test_uniqueness_of_entity(self):
        cached = recipes.cached_entity.make()
        with pytest.raises(IntegrityError):
            recipes.cached_entity.make(entity=cached.entity)


@pytest.mark.django_db
class TestEntityCacheModelsVisibility:
    def test_entity_visibility(self):
        version = recipes.cached_entity_version.make(visibility='restricted')
        assert version.entity.visibility == 'restricted'

    def test_entity_visibility_is_private_if_no_versions(self):
        cached = recipes.cached_entity.make()
        assert cached.visibility == 'private'

    def test_get_version(self):
        version = recipes.cached_entity_version.make()
        assert version.entity.get_version(version.sha) == version

    def test_set_entity_version_visibility(self):
        version = recipes.cached_entity_version.make()
        version.set_visibility('restricted')
        version.refresh_from_db()
        assert version.visibility == 'restricted'

    def test_add_version(self, helpers):
        model = recipes.model.make()
        commit = helpers.add_version(model, visibility='restricted', cache=False)

        assert model.repocache.versions.count() == 0
        model.repocache.add_version(commit.hexsha)

        version = model.repocache.get_version(commit.hexsha)
        assert version.sha == commit.hexsha
        assert version.timestamp == commit.committed_at
        assert version.visibility == 'restricted'
