import pytest
from django.db.utils import IntegrityError

from core import recipes
from datasets.models import Dataset


@pytest.mark.django_db
class TestDataset:
    def test_str(self):
        dataset = recipes.dataset.make(name='test dataset')
        assert str(dataset) == 'test dataset'

    def test_related_protocol(self, user):
        protocol = recipes.protocol.make(author=user)
        dataset = recipes.dataset.make(author=user, name='mydataset', protocol=protocol)
        assert dataset.protocol == protocol

    @pytest.mark.django_db
    def test_visibility_and_sharing(self, logged_in_user, other_user, anon_user):
        protocol = recipes.protocol.make()
        recipes.dataset.make(author=logged_in_user, name='mydataset', visibility='public', protocol=protocol)
        assert Dataset.objects.visible_to_user(logged_in_user).count() == 1
        assert Dataset.objects.visible_to_user(anon_user).count() == 1
        recipes.dataset.make(author=logged_in_user, name='mydataset2', visibility='private', protocol=protocol)
        assert Dataset.objects.visible_to_user(logged_in_user).count() == 2
        assert Dataset.objects.visible_to_user(anon_user).count() == 1
        recipes.dataset.make(author=other_user, name='mydataset3', visibility='public', protocol=protocol)
        assert Dataset.objects.visible_to_user(logged_in_user).count() == 3
        assert Dataset.objects.visible_to_user(anon_user).count() == 2
        recipes.dataset.make(author=other_user, name='mydataset4', visibility='moderated', protocol=protocol)
        assert Dataset.objects.visible_to_user(logged_in_user).count() == 4
        assert Dataset.objects.visible_to_user(anon_user).count() == 3
        recipes.dataset.make(author=other_user, name='mydataset5', visibility='private', protocol=protocol)
        assert Dataset.objects.visible_to_user(logged_in_user).count() == 4
        assert Dataset.objects.visible_to_user(anon_user).count() == 3

        # TODO - No testing of shared datasets - waiting for implementation in front end


@pytest.mark.django_db
class TestDatasetNameUniqueness:
    def test_user_cannot_have_same_named_dataset(self, user):
        recipes.dataset.make(author=user, name='mydataset')

        with pytest.raises(IntegrityError):
            Dataset.objects.create(author=user, name='mydataset')

    def test_different_users_can_have_same_named_model(self, user, other_user):
        recipes.dataset.make(author=user, name='mydataset')
        other_dataset = recipes.dataset.make(author=other_user, name='mydataset')
        assert other_dataset
