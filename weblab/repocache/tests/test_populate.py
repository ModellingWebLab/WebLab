import pytest

from core import recipes
from repocache.populate import populate_entity_cache


@pytest.mark.django_db
def test_populate(model_with_version):
    model_with_version.repo.tag('v1')

    populate_entity_cache(model_with_version)

    cached = model_with_version.cachedentity

    assert cached is not None
    sha = model_with_version.repo.latest_commit.hexsha
    assert list(cached.versions.values_list('sha', flat=True)) == [sha]
    assert list(cached.tags.values_list('tag', flat=True)) == ['v1']
    assert cached.latest_version.sha == sha


@pytest.mark.django_db
def test_populate_removes_old_versions():
    model = recipes.model.make()
    cached = recipes.cached_entity_version.make(entity__entity=model).entity
    recipes.cached_entity_tag.make(entity=cached)

    assert cached.versions.exists()
    assert cached.tags.exists()

    populate_entity_cache(model)

    assert not cached.versions.exists()
    assert not cached.tags.exists()
