import pytest

from core import recipes
from repocache.populate import populate_entity_cache


@pytest.mark.django_db
def test_populate(model_with_version):
    model_with_version.repo.tag('v1')

    populate_entity_cache(model_with_version)

    cached = model_with_version.cachedentity

    assert cached is not None
    latest = model_with_version.repo.latest_commit

    version = cached.versions.get()
    assert version.sha == latest.hexsha
    assert version.timestamp == latest.committed_at

    assert cached.tags.get().tag == 'v1'

    assert cached.latest_version.sha == latest.hexsha


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
