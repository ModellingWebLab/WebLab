from datetime import date

import pytest
from django.db.utils import IntegrityError
from django.shortcuts import get_object_or_404
from guardian.shortcuts import assign_perm

from core import recipes
from datasets.models import Dataset
from repocache.models import CachedFittingSpec
from repocache.populate import populate_entity_cache


@pytest.mark.django_db
class TestNameUniqueness:
    def test_user_cannot_have_same_named_fittingspec(self, user):
        spec = recipes.fittingspec.make(author=user, name='myspec')
        assert str(spec) == 'myspec'

        with pytest.raises(IntegrityError):
            recipes.fittingspec.make(author=user, name='myspec')

    def test_user_can_have_same_named_fittingspec_and_other_entities(self, user):
        recipes.fittingspec.make(author=user, name='myentity')
        recipes.model.make(author=user, name='myentity')
        recipes.protocol.make(author=user, name='myentity')

    def test_different_users_can_have_same_named_fittingspec(self, user, other_user):
        recipes.fittingspec.make(author=user, name='myspec')
        assert recipes.fittingspec.make(author=other_user, name='myspec')


@pytest.mark.django_db
def test_permissions():
    user, other_user = recipes.user.make(_quantity=2)
    superuser = recipes.user.make(is_superuser=True)
    fittingspec = recipes.fittingspec.make(author=user)

    assert fittingspec.viewers == {user}

    assert not fittingspec.is_editable_by(user)
    assert fittingspec.is_editable_by(superuser)
    assert not fittingspec.is_editable_by(other_user)

    assign_perm('entities.create_fittingspec', user)
    user = get_object_or_404(user.__class__, pk=user.id)  # Reset permission cache!
    assert fittingspec.is_editable_by(user)

    assert fittingspec.is_deletable_by(user)
    assert fittingspec.is_deletable_by(superuser)
    assert not fittingspec.is_deletable_by(other_user)

    fittingspec.add_collaborator(other_user)
    assert other_user in fittingspec.collaborators
    assert fittingspec.viewers == {user, other_user}
    assert not fittingspec.is_editable_by(other_user)
    assert not fittingspec.is_deletable_by(other_user)

    assign_perm('entities.create_fittingspec', other_user)
    other_user = get_object_or_404(user.__class__, pk=other_user.id)  # Reset permission cache!
    assert fittingspec.is_editable_by(other_user)

    fittingspec.remove_collaborator(other_user)
    assert other_user not in fittingspec.collaborators
    assert not fittingspec.is_editable_by(other_user)
    assert not fittingspec.is_deletable_by(other_user)


@pytest.mark.django_db
class TestRepository:
    def test_repo_path_create_and_delete(self, fake_repo_path):
        spec = recipes.fittingspec.make()
        path = fake_repo_path / str(spec.author.pk) / 'fittingspecs' / str(spec.pk)

        assert spec.repo._root == str(path)
        assert spec.repo_abs_path == path

    def test_repo_is_deleted(self):
        spec = recipes.fittingspec.make()
        assert spec.repo_abs_path.exists()
        spec.delete()
        assert not spec.repo_abs_path.exists()

    def test_get_repocache(self):
        spec = recipes.fittingspec.make()
        assert CachedFittingSpec.objects.count() == 0
        assert spec.repocache
        assert CachedFittingSpec.objects.count() == 1
        assert spec.repocache
        assert CachedFittingSpec.objects.count() == 1
        spec.delete()
        assert CachedFittingSpec.objects.count() == 0


@pytest.mark.django_db
class TestFittingResult:
    def test_name(self, helpers):
        model = recipes.model.make(name='my model')
        protocol = recipes.protocol.make(name='my protocol')
        dataset = recipes.dataset.make(name='my dataset')
        fittingspec = recipes.fittingspec.make(name='my fitting spec')

        model_version = helpers.add_version(model, tag_name='v1')
        protocol_version = helpers.add_version(protocol, tag_name='v2')
        fittingspec_version = helpers.add_version(fittingspec, tag_name='v3')

        fitres = recipes.fittingresult.make(
            model=model,
            model_version=model.repocache.get_version(model_version.sha),
            protocol=protocol,
            protocol_version=protocol.repocache.get_version(protocol_version.sha),
            fittingspec=fittingspec,
            fittingspec_version=fittingspec.repocache.get_version(fittingspec_version.sha),
            dataset=dataset,
        )

        assert str(fitres) == fitres.name == 'Fit my model to my dataset using my fitting spec'

    def test_latest_version(self):
        v1 = recipes.fittingresult_version.make(created_at=date(2017, 1, 2))
        v2 = recipes.fittingresult_version.make(fittingresult=v1.fittingresult, created_at=date(2017, 1, 3))

        assert v1.fittingresult.latest_version == v2
        assert not v1.is_latest
        assert v2.is_latest

    def test_latest_result(self):
        ver = recipes.fittingresult_version.make(created_at=date(2017, 1, 2), status='FAILED')

        assert ver.fittingresult.latest_result == 'FAILED'

    def test_latest_result_empty_if_no_versions(self):
        fitres = recipes.fittingresult.make()

        assert fitres.latest_result == ''

    def test_nice_versions(self, fittingresult_version):
        fitres = fittingresult_version.fittingresult

        assert fitres.nice_model_version == fitres.model.repocache.latest_version.sha[:8] + '...'
        assert fitres.nice_protocol_version == fitres.protocol.repocache.latest_version.sha[:8] + '...'

        fitres.model.repo.tag('v1')
        populate_entity_cache(fitres.model)
        assert fitres.nice_model_version == 'v1'

        fitres.protocol.repo.tag('v2')
        populate_entity_cache(fitres.protocol)

        assert fitres.nice_protocol_version == 'v2'

    def test_visibility(self, helpers):
        model = recipes.model.make()
        protocol = recipes.protocol.make()
        ds1 = recipes.dataset.make(visibility='private')
        ds2 = recipes.dataset.make(visibility='public')
        fittingspec = recipes.fittingspec.make()

        mv1 = helpers.add_cached_version(model, visibility='private')
        mv2 = helpers.add_cached_version(model, visibility='public')
        pv1 = helpers.add_cached_version(protocol, visibility='private')
        pv2 = helpers.add_cached_version(protocol, visibility='public')
        fv1 = helpers.add_cached_version(fittingspec, visibility='private')
        fv2 = helpers.add_cached_version(fittingspec, visibility='public')

        # all public
        assert recipes.fittingresult.make(
            model=model, model_version=mv2,
            protocol=protocol, protocol_version=pv2,
            fittingspec=fittingspec, fittingspec_version=fv2,
            dataset=ds2,
        ).visibility == 'public'

        # all private
        assert recipes.fittingresult.make(
            model=model, model_version=mv1,
            protocol=protocol, protocol_version=pv1,
            fittingspec=fittingspec, fittingspec_version=fv1,
            dataset=ds1,
        ).visibility == 'private'

        # model private version => private
        assert recipes.fittingresult.make(
            model=model, model_version=mv1,
            protocol=protocol, protocol_version=pv2,
            fittingspec=fittingspec, fittingspec_version=fv2,
            dataset=ds2,
        ).visibility == 'private'

        # protocol private version => private
        assert recipes.fittingresult.make(
            model=model, model_version=mv2,
            protocol=protocol, protocol_version=pv1,
            fittingspec=fittingspec, fittingspec_version=fv2,
            dataset=ds2,
        ).visibility == 'private'

        # fitting spec private version => private
        assert recipes.fittingresult.make(
            model=model, model_version=mv2,
            protocol=protocol, protocol_version=pv2,
            fittingspec=fittingspec, fittingspec_version=fv1,
            dataset=ds2,
        ).visibility == 'private'

        # dataset private version => private
        assert recipes.fittingresult.make(
            model=model, model_version=mv2,
            protocol=protocol, protocol_version=pv2,
            fittingspec=fittingspec, fittingspec_version=fv2,
            dataset=ds1,
        ).visibility == 'private'

    def test_viewers(self, helpers, user):
        helpers.add_permission(user, 'create_model')
        helpers.add_permission(user, 'create_protocol')
        helpers.add_permission(user, 'create_fittingspec')
        helpers.add_permission(user, 'create_dataset', model=Dataset)

        model = recipes.model.make()
        protocol = recipes.protocol.make()
        fittingspec = recipes.fittingspec.make()
        # Datasets do not currently support collaborators
        # (https://github.com/ModellingWebLab/WebLab/issues/247)
        # so test with a public dataset for now
        dataset = recipes.dataset.make(visibility='public')
        mv = helpers.add_cached_version(model, visibility='private')
        pv = helpers.add_cached_version(protocol, visibility='private')
        fv = helpers.add_cached_version(fittingspec, visibility='private')

        fr = recipes.fittingresult.make(
            model=model, model_version=mv,
            protocol=protocol, protocol_version=pv,
            fittingspec=fittingspec, fittingspec_version=fv,
            dataset=dataset,
        )
        assert user not in fr.viewers
        assert not fr.is_visible_to_user(user)

        fr.model.add_collaborator(user)
        assert user not in fr.viewers
        assert not fr.is_visible_to_user(user)

        fr.protocol.add_collaborator(user)
        assert user not in fr.viewers
        assert not fr.is_visible_to_user(user)

        fr.fittingspec.add_collaborator(user)
        assert user in fr.viewers
        assert fr.is_visible_to_user(user)

    def test_viewers_of_public_fittingresult(self, helpers, user):
        model = recipes.model.make()
        protocol = recipes.protocol.make()
        fittingspec = recipes.fittingspec.make()
        dataset = recipes.dataset.make(visibility='public')
        mv = helpers.add_cached_version(model, visibility='public')
        pv = helpers.add_cached_version(protocol, visibility='public')
        fv = helpers.add_cached_version(fittingspec, visibility='public')

        fr = recipes.fittingresult.make(
            model=model, model_version=mv,
            protocol=protocol, protocol_version=pv,
            fittingspec=fittingspec, fittingspec_version=fv,
            dataset=dataset,
        )
        assert fr.viewers == {}
