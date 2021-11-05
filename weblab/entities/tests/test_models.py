import os

import pytest
from django.db.utils import IntegrityError

from core import recipes
from entities.models import Entity, ModelEntity, ProtocolEntity, ModelGroup
from repocache.exceptions import RepoCacheMiss
from repocache.models import CachedModel
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
def test_deletion_permissions():
    user, other_user = recipes.user.make(_quantity=2)
    model = recipes.model.make(author=user)
    superuser = recipes.user.make(is_superuser=True)

    assert model.is_deletable_by(user)
    assert model.is_deletable_by(superuser)
    assert not model.is_deletable_by(other_user)


@pytest.mark.django_db
def test_visibility_and_sharing(user, anon_user, other_user, admin_user, helpers):
    """Checks the EntityManager visible_to_user and shared_with_user methods."""
    # Own entities -> always visible
    own_models = recipes.model.make(author=user, _quantity=3)
    helpers.add_fake_version(own_models[0], 'moderated')
    helpers.add_fake_version(own_models[1], 'public')
    helpers.add_fake_version(own_models[2], 'private')
    # Other entity type shouldn't show up
    own_protocol = recipes.protocol.make(author=user)
    helpers.add_fake_version(own_protocol, 'moderated')
    # Non-shared public/moderated entities -> visible
    other_public_models = recipes.model.make(author=other_user, _quantity=2)
    helpers.add_fake_version(other_public_models[0], 'moderated')
    helpers.add_fake_version(other_public_models[1], 'public')
    # Non-shared private entities -> not visible
    other_private_model = recipes.model.make(author=other_user)
    helpers.add_fake_version(other_private_model, 'private')
    # Shared public or private entities -> visible
    other_shared_model = recipes.model.make(author=other_user)
    helpers.add_fake_version(other_private_model, 'private')
    other_shared_model.add_collaborator(user)
    other_shared_protocol = recipes.protocol.make(author=other_user)
    helpers.add_fake_version(other_shared_protocol, 'private')
    other_shared_protocol.add_collaborator(user)

    # Getting shared entities just shows those shared explicitly, of the correct type
    assert list(ModelEntity.objects.shared_with_user(user).all()) == [other_shared_model]

    # Check visible entities are correct
    visible_models = ModelEntity.objects.visible_to_user(user).all()
    assert visible_models.count() == 6
    assert set(visible_models) == set(own_models + other_public_models + [other_shared_model])

    # Anonymous users only see public things
    visible_to_anon = ModelEntity.objects.visible_to_user(anon_user).all()
    assert visible_to_anon.count() == 4
    assert set(visible_to_anon) == set(own_models[:2] + other_public_models)

    # Admins don't get special visibility rights, so only see public entities
    visible_to_admin = ModelEntity.objects.visible_to_user(admin_user).all()
    assert visible_to_admin.count() == 4
    assert set(visible_to_admin) == set(own_models[:2] + other_public_models)


@pytest.mark.django_db
class TestEntity:
    def test_str(self):
        model = recipes.model.make(name='test model')
        assert str(model) == 'test model'

    def test_repo_abs_path(self, fake_repo_path):
        model = recipes.model.make()
        path = os.path.join(str(fake_repo_path), str(model.author.pk), 'models', str(model.pk))

        assert model.repo._root == path
        assert str(model.repo_abs_path) == path

    def test_set_and_get_version_visibility(self, model_with_version):
        commit = model_with_version.repo.latest_commit
        assert model_with_version.get_version_visibility(commit.sha) == 'private'

        model_with_version.set_version_visibility(commit.sha, 'public')

        assert model_with_version.get_version_visibility(commit.sha) == 'public'

    def test_get_and_set_visibility_in_repo(self, helpers):
        model = recipes.model.make()
        commit = helpers.add_version(model, cache=False)
        assert model.get_visibility_from_repo(commit) is None

        model.set_visibility_in_repo(commit, 'public')
        assert model.get_visibility_from_repo(commit) == 'public'
        assert commit.get_note() == 'Visibility: public'

    def test_get_repocache(self):
        model = recipes.model.make()
        assert CachedModel.objects.count() == 0
        assert model.repocache
        assert CachedModel.objects.count() == 1
        assert model.repocache
        assert CachedModel.objects.count() == 1

    def test_entity_visibility_gets_latest_visibility_from_cache(self):
        model = recipes.model.make()
        recipes.cached_model_version.make(
            entity__entity=model,
            sha='test-sha',
            visibility='public'
        )

        assert model.visibility == 'public'

    def test_get_version_visibility_fetches_from_cache(self):
        model = recipes.model.make()
        recipes.cached_model_version.make(
            entity__entity=model,
            sha='test-sha',
            visibility='public'
        )

        assert model.get_version_visibility('test-sha') == 'public'

    def test_get_version_visiblity_uses_default(self):
        model = recipes.model.make()
        model.get_version_visibility('non-existent-sha', default='public') == 'public'

    def test_get_version_visiblity_raises_if_no_default(self):
        model = recipes.model.make()
        with pytest.raises(RepoCacheMiss):
            model.get_version_visibility('non-existent-sha')

    def test_set_version_visibility_updates_cache(self, helpers):
        model = recipes.model.make()
        sha = helpers.add_version(model).sha

        populate_entity_cache(model)

        model.set_version_visibility(sha, 'public')

        assert model.cachedentity.versions.get().visibility == 'public'

    def test_get_ref_version_visibility(self, helpers):
        model = recipes.model.make()
        sha = helpers.add_version(model, visibility='public').sha
        model.add_tag('v1', sha)

        assert model.get_ref_version_visibility(sha) == 'public'
        assert model.get_ref_version_visibility('v1') == 'public'
        assert model.get_ref_version_visibility('latest') == 'public'

    def test_get_ref_version_visibility_invalid_hexsha(self, helpers):
        model = recipes.model.make()
        helpers.add_version(model, visibility='public').sha

        with pytest.raises(RepoCacheMiss):
            model.get_ref_version_visibility('0' * 40)

    def test_is_valid_sha(self):
        assert Entity._is_valid_sha('0' * 40)
        assert not Entity._is_valid_sha('0' * 39)
        assert not Entity._is_valid_sha('g' * 40)

    def test_get_ref_version_visibility_invalid_tag(self, helpers):
        model = recipes.model.make()
        helpers.add_version(model, visibility='public').sha

        with pytest.raises(RepoCacheMiss):
            model.get_ref_version_visibility('v10')

    def test_add_tag(self, helpers):
        model = recipes.model.make()
        sha = helpers.add_version(model).sha
        populate_entity_cache(model)

        model.add_tag('mytag', sha)

        assert model.cachedentity.tags.get().tag == 'mytag'
        assert model.repo.tag_dict[sha][0].name == 'mytag'

        assert model.get_tags(sha) == {'mytag'}

    def test_entity_repo_is_deleted_when_entity_is_deleted(self, model_with_version):
        repo_path = model_with_version.repo_abs_path
        assert repo_path.exists()

        model_with_version.delete()

        assert not repo_path.exists()


@pytest.mark.django_db
class TestModelGroup:
    def test_user_cannot_have_same_named_model_group(self, user):
        recipes.modelgroup.make(author=user, title='mymodelgroup')

        with pytest.raises(IntegrityError):
            ModelGroup.objects.create(author=user, title='mymodelgroup')

    def test_user_can_have_same_named_model_protocol_and_model_group(self, user):
        ModelEntity.objects.create(author=user, name='myentity')
        ProtocolEntity.objects.create(author=user, name='myentity')
        ModelGroup.objects.create(author=user, title='mymodelgroup')

    def test_different_users_can_have_same_named_model_group(self, user, other_user):
        ModelEntity.objects.create(author=user, name='mymodel')
        assert ModelEntity.objects.create(author=other_user, name='mymodel')

    def test_str(self, user):
        model = recipes.model.make(name='test model')
        modelgroup = recipes.modelgroup.make(author=user, models=[model], title="test model group")
        assert str(modelgroup) == 'test model group'
        assert [str(m) for m in modelgroup.models.all()] == ["test model"]

    def test_visibility_and_sharing(self, user, other_user, admin_user):
        """Checks the is_editable_by method."""
        def check_own_user(model_groups, user):
            assert all([modelgroup.visible_to_user(user) for modelgroup in model_groups])
            assert all([modelgroup.is_editable_by(user) for modelgroup in model_groups])
            assert all([modelgroup.is_visibility_editable_by(user) for modelgroup in model_groups])
            assert all([modelgroup.is_deletable_by(user) for modelgroup in model_groups])
            assert all([modelgroup.is_managed_by(user) for modelgroup in model_groups])

        # Check user permissions
        model_groups = recipes.modelgroup.make(author=user, _quantity=2, visibility='private')
        check_own_user(model_groups, user)
        assert all([modelgroup.viewers == {user} for modelgroup in model_groups])
        assert all([modelgroup.collaborators == [] for modelgroup in model_groups])

        # Check other user permissions
        assert not any([modelgroup.visible_to_user(other_user) for modelgroup in model_groups])
        assert not any([modelgroup.is_editable_by(other_user) for modelgroup in model_groups])
        assert not any([modelgroup.is_visibility_editable_by(other_user) for modelgroup in model_groups])
        assert not any([modelgroup.is_deletable_by(other_user) for modelgroup in model_groups])
        assert not any([modelgroup.is_managed_by(other_user) for modelgroup in model_groups])

        # Check permissions after adding as collaborator
        for modelgroup in model_groups:
            modelgroup.add_collaborator(other_user)
        check_own_user(model_groups, user)
        assert all([modelgroup.collaborators == [other_user] for modelgroup in model_groups])
        assert all([modelgroup.viewers == {user, other_user} for modelgroup in model_groups])
        assert all([modelgroup.visible_to_user(other_user) for modelgroup in model_groups])
        assert all([modelgroup.is_editable_by(other_user) for modelgroup in model_groups])
        assert not any([modelgroup.is_visibility_editable_by(other_user) for modelgroup in model_groups])
        assert not any([modelgroup.is_managed_by(other_user) for modelgroup in model_groups])

        # Check permissions after removing as collaborator
        for modelgroup in model_groups:
            modelgroup.remove_collaborator(other_user)
        check_own_user(model_groups, user)
        assert all([modelgroup.viewers == {user} for modelgroup in model_groups])
        assert all([modelgroup.collaborators == [] for modelgroup in model_groups])
        assert not any([modelgroup.visible_to_user(other_user) for modelgroup in model_groups])

        # Check permissions after changing visibility
        model_groups[0].visibility = 'public'
        model_groups[1].visibility = 'moderted'
        check_own_user(model_groups, user)
        assert all([modelgroup.viewers == {user} for modelgroup in model_groups])
        assert all([modelgroup.collaborators == [] for modelgroup in model_groups])
        assert all([modelgroup.visible_to_user(other_user) for modelgroup in model_groups])
