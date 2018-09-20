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
