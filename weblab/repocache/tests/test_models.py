import pytest
from django.db.utils import IntegrityError

from core import recipes
from repocache.exceptions import RepoCacheMiss
from repocache.models import (
    CachedFittingSpec,
    CachedModel,
    CachedModelVersion,
    CachedProtocol,
)
from repocache.populate import populate_entity_cache


@pytest.mark.django_db
class TestEntityCacheModels:
    @pytest.mark.parametrize("recipe,manager", [
        (recipes.cached_model, CachedModel.objects),
        (recipes.cached_protocol, CachedProtocol.objects),
        (recipes.cached_fittingspec, CachedFittingSpec.objects),
    ])
    def test_cachedentity_is_deleted_when_entity_is_deleted(self, recipe, manager):
        cached = recipe.make()
        cached.entity.delete()
        assert not manager.filter(pk=cached.pk).exists()

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_version),
        (recipes.cached_protocol_version),
        (recipes.cached_fittingspec_version),
    ])
    def test_related_names_for_versions(self, recipe):
        version = recipe.make()
        assert list(version.entity.versions.all()) == [version]

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_tag),
        (recipes.cached_protocol_tag),
        (recipes.cached_fittingspec_tag),
    ])
    def test_related_names_for_tags(self, recipe):
        tag = recipe.make()
        assert list(tag.entity.tags.all()) == [tag]

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_version),
        (recipes.cached_protocol_version),
        (recipes.cached_fittingspec_version),
    ])
    def test_uniqueness_of_entity_and_version_sha(self, recipe):
        version = recipe.make()
        with pytest.raises(IntegrityError):
            recipe.make(entity=version.entity, sha=version.sha)

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_tag),
        (recipes.cached_protocol_tag),
        (recipes.cached_fittingspec_tag),
    ])
    def test_uniqueness_of_entity_and_tag(self, recipe):
        version = recipe.make()
        with pytest.raises(IntegrityError):
            recipe.make(entity=version.entity, tag=version.tag)

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model),
        (recipes.cached_protocol),
        (recipes.cached_fittingspec),
    ])
    def test_uniqueness_of_entity(self, recipe):
        cached = recipe.make()
        with pytest.raises(IntegrityError):
            recipe.make(entity=cached.entity)

    @pytest.mark.parametrize("recipe,property_name", [
        (recipes.cached_model_version, 'model'),
        (recipes.cached_protocol_version, 'protocol'),
        (recipes.cached_fittingspec_version, 'fittingspec'),
    ])
    def test_entity_property(self, recipe, property_name):
        cached = recipe.make()
        assert getattr(cached, property_name) == cached.entity.entity


@pytest.mark.django_db
class TestEntityCacheModelsVisibility:
    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_version),
        (recipes.cached_protocol_version),
        (recipes.cached_fittingspec_version),
    ])
    def test_entity_visibility(self, recipe):
        version = recipe.make(visibility='public')
        assert version.entity.visibility == 'public'

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model),
        (recipes.cached_protocol),
        (recipes.cached_fittingspec),
    ])
    def test_entity_visibility_is_private_if_no_versions(self, recipe):
        cached = recipe.make()
        assert cached.visibility == 'private'

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_version),
        (recipes.cached_protocol_version),
        (recipes.cached_fittingspec_version),
    ])
    def test_get_version(self, recipe):
        version = recipe.make()
        assert version.entity.get_version(version.sha) == version

    @pytest.mark.parametrize("recipe", [
        (recipes.cached_model_version),
        (recipes.cached_protocol_version),
        (recipes.cached_fittingspec_version),
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

    def test_get_name_for_version(self, helpers):
        model = recipes.model.make()
        commit = helpers.add_version(model, visibility='public', cache=False)
        populate_entity_cache(model)
        assert model.repocache.get_name_for_version(commit.sha) == commit.sha
        assert model.repocache.get_name_for_version('latest') == 'latest'

        model.repo.tag('v1')
        assert model.repocache.get_name_for_version(commit.sha) == commit.sha
        populate_entity_cache(model)
        assert model.repocache.get_name_for_version(commit.sha) == 'v1'
        assert model.repocache.get_name_for_version('latest') == 'v1'
        assert model.repocache.get_name_for_version('v1') == 'v1'
        with pytest.raises(RepoCacheMiss):
            model.repocache.get_name_for_version('random value')

    def test_nice_version(self, model_with_version):
        version = model_with_version.cachedentity.latest_version
        assert version.nice_version() == '%s...' % version.sha[:8]

        model_with_version.repo.tag('v1')
        populate_entity_cache(model_with_version)
        assert version.nice_version() == 'v1'


@pytest.mark.django_db
class TestCachedEntityVersionVisibleToUser:
    def test_visibility_and_sharing(self, user, anon_user, other_user, admin_user, helpers):
        # Own entities -> always visible
        own_models = recipes.model.make(author=user, _quantity=3)
        own_moderated_version = helpers.add_fake_version(own_models[0], 'moderated')
        own_public_version = helpers.add_fake_version(own_models[1], 'public')
        own_private_version = helpers.add_fake_version(own_models[2], 'private')

        # Other entity type shouldn't show up
        own_protocol = recipes.protocol.make(author=user)
        helpers.add_fake_version(own_protocol, 'moderated')

        # Non-shared public/moderated entities -> visible
        other_public_models = recipes.model.make(author=other_user, _quantity=2)
        other_moderated_version = helpers.add_fake_version(other_public_models[0], 'moderated')
        other_public_version = helpers.add_fake_version(other_public_models[1], 'public')

        # Non-shared private entities -> not visible
        other_private_model = recipes.model.make(author=other_user)
        other_private_version = helpers.add_fake_version(other_private_model, 'private')  # noqa: F841

        # Shared public or private entities -> visible
        other_shared_model = recipes.model.make(author=other_user)
        other_shared_version = helpers.add_fake_version(other_shared_model, 'private')
        other_shared_model.add_collaborator(user)

        other_shared_protocol = recipes.protocol.make(author=other_user)
        helpers.add_fake_version(other_shared_protocol, 'private')
        other_shared_protocol.add_collaborator(user)

        # User can see own versions, plus public, plus those explicitly shared
        visible_to_self = CachedModelVersion.objects.visible_to_user(user).all()
        assert visible_to_self.count() == 6
        assert set(visible_to_self) == {
            own_moderated_version, own_public_version, own_private_version,
            other_moderated_version, other_public_version,
            other_shared_version
        }

#        # Anonymous users only see public things
        visible_to_anon = CachedModelVersion.objects.visible_to_user(anon_user).all()
        assert visible_to_anon.count() == 4
        assert set(visible_to_anon) == {
            own_moderated_version, own_public_version,
            other_moderated_version, other_public_version,
        }

        # Admins don't get special visibility rights, so only see public entities
        visible_to_admin = CachedModelVersion.objects.visible_to_user(admin_user).all()
        assert visible_to_admin.count() == 4
        assert set(visible_to_admin) == {
            own_moderated_version, own_public_version,
            other_moderated_version, other_public_version,
        }
