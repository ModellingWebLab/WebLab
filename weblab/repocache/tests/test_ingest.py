import pytest

from core import recipes
from repocache.ingest import index_entity_repo


@pytest.mark.django_db
def test_index_repo(model_with_version):
    model_with_version.repo.tag('v1')

    index_entity_repo(model_with_version)

    cached = model_with_version.cachedentity

    assert cached is not None
    sha = model_with_version.repo.latest_commit.hexsha
    assert list(cached.versions.values_list('sha', flat=True)) == [sha]
    assert list(cached.tags.values_list('tag', flat=True)) == ['v1']
    assert cached.latest_version.sha == sha


@pytest.mark.django_db
def test_index_repo_removes_old_versions():
    model = recipes.model.make()
    cached = recipes.cached_entity_version.make(entity__entity=model).entity
    recipes.cached_entity_tag.make(entity=cached)

    assert cached.versions.exists()
    assert cached.tags.exists()

    index_entity_repo(model)

    assert not cached.versions.exists()
    assert not cached.tags.exists()
