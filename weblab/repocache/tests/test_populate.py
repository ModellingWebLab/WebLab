import pytest

from core import recipes
from repocache.populate import populate_entity_cache


@pytest.mark.django_db
class TestPopulate:
    def test_populate(self, model_with_version):
        model_with_version.repo.tag('v1')

        populate_entity_cache(model_with_version)

        cached = model_with_version.cachedentity

        assert cached is not None
        latest = model_with_version.repo.latest_commit

        version = cached.versions.get()
        assert version.sha == latest.hexsha
        assert version.timestamp == latest.committed_at

        assert cached.tags.get().tag == 'v1'

    def test_removes_old_versions(self):
        model = recipes.model.make()
        cached = recipes.cached_entity_version.make(entity__entity=model).entity
        recipes.cached_entity_tag.make(entity=cached)

        assert cached.versions.exists()
        assert cached.tags.exists()

        populate_entity_cache(model)

        assert not cached.versions.exists()
        assert not cached.tags.exists()

    def test_falls_back_to_older_visibilities(self, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public', cache=False)
        v2 = helpers.add_version(model, cache=False)
        v3 = helpers.add_version(model, visibility='private', cache=False)
        v4 = helpers.add_version(model, cache=False)

        populate_entity_cache(model)

        assert model.repocache.get_version(v1.hexsha).visibility == 'public'
        assert model.repocache.get_version(v2.hexsha).visibility == 'public'
        assert model.repocache.get_version(v3.hexsha).visibility == 'private'
        assert model.repocache.get_version(v4.hexsha).visibility == 'private'

    def test_falls_back_to_private(self, helpers):
        model = recipes.model.make()
        commit = helpers.add_version(model)

        populate_entity_cache(model)

        assert model.repocache.get_version(commit.hexsha).visibility == 'private'

    def test_applies_missing_visibilities(self, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        v2 = helpers.add_version(model)
        v3 = helpers.add_version(model)

        populate_entity_cache(model)

        assert v1.get_note() == 'Visibility: public'
        assert v2.get_note() == 'Visibility: public'
        assert v3.get_note() == 'Visibility: public'
