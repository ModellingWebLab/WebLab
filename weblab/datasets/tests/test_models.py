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
class TestDatasetNameUniqueness:
    def test_user_cannot_have_same_named_dataset(self, user):
        recipes.dataset.make(author=user, name='mydataset')

        with pytest.raises(IntegrityError):
            Dataset.objects.create(author=user, name='mydataset')

    def test_different_users_can_have_same_named_model(self, user, other_user):
        recipes.dataset.make(author=user, name='mydataset')
        other_dataset = recipes.dataset.make(author=other_user, name='mydataset')
        assert other_dataset
