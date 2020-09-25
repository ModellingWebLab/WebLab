import pytest

from core import recipes
from weblab.fitting.models import FittingSpec


@pytest.mark.django_db
class TestEntityRenaming:
    def test_fittingspec_renaming_success(self, client, logged_in_user, helpers):

        fittingspec = recipes.fittingspec.make(author=logged_in_user)
        assert fittingspec.name == 'my dataset1'

        response = client.post(
            '/fittingspec/%d/rename' % fittingspec.pk,
            data={
                     'name': 'new name'
                 })
        assert response.status_code == 302
        fittingspec = FittingSpec.objects.first()
        assert fittingspec.name == 'new name'

    def test_fittingspec_renaming_different_users_succeeds(self, client, logged_in_user, helpers):
        dataset = recipes.dataset.make(author=logged_in_user)

        dataset2 = recipes.dataset.make(name='test dataset 2')
        assert dataset.name == 'my dataset1'
        assert dataset2.name == 'test dataset 2'

        response = client.post(
            '/datasets/%d/rename' % dataset.pk,
            data={
                     'name': 'test dataset 2'
                 })
        assert response.status_code == 302
        dataset = Dataset.objects.first()
        assert dataset.name == 'test dataset 2'

    def test_fittingspec_renaming_same_users_fails(self, client, logged_in_user, helpers):
        dataset = recipes.dataset.make(author=logged_in_user)

        dataset2 = recipes.dataset.make(author=logged_in_user, name='test dataset 2')
        assert dataset.name == 'my dataset1'
        assert dataset2.name == 'test dataset 2'

        response = client.post(
            '/datasets/%d/rename' % dataset.pk,
            data={
                     'name': 'test dataset 2'
                 })
        assert response.status_code == 200
        dataset = Dataset.objects.first()
        assert dataset.name == 'my dataset1'
