import pytest

from core import recipes
from fitting.models import FittingSpec


@pytest.mark.django_db
class TestFittingSpecRenaming:
    def test_fittingspec_renaming_success(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_fittingspec')
        fittingspec = recipes.fittingspec.make(author=logged_in_user)
        assert fittingspec.name == 'my spec1'

        response = client.post(
            '/fitting/specs/%d/rename' % fittingspec.pk,
            data={
                'name': 'new name'
            })
        assert response.status_code == 302
        fittingspec2 = FittingSpec.objects.first()
        assert fittingspec2.name == "new name"

    def test_fittingspec_renaming_different_users_succeeds(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_fittingspec')
        fittingspec = recipes.fittingspec.make(author=logged_in_user)

        fittingspec2 = recipes.fittingspec.make(name='test fittingspec 2')
        assert fittingspec.name == 'my spec1'
        assert fittingspec2.name == 'test fittingspec 2'

        response = client.post(
            '/fitting/specs/%d/rename' % fittingspec.pk,
            data={
                'name': 'test fittingspec 2'
            })
        assert response.status_code == 302
        fittingspec = FittingSpec.objects.first()
        assert fittingspec.name == 'test fittingspec 2'

    def test_dataset_renaming_same_users_fails(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_fittingspec')
        fittingspec = recipes.fittingspec.make(author=logged_in_user)
        fittingspec2 = recipes.fittingspec.make(author=logged_in_user, name='test fittingspec 2')
        assert fittingspec.name == 'my spec1'
        assert fittingspec2.name == 'test fittingspec 2'

        response = client.post(
            '/fitting/specs/%d/rename' % fittingspec.pk,
            data={
                'name': 'test fittingspec 2'
            })
        assert response.status_code == 200
        fittingspec = FittingSpec.objects.first()
        assert fittingspec.name == 'my spec1'
