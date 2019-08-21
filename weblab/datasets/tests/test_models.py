import pytest
from django.db.utils import IntegrityError

from core import recipes
from datasets.models import Dataset
from repocache.exceptions import RepoCacheMiss
from repocache.models import CachedEntity
from repocache.populate import populate_entity_cache


@pytest.mark.django_db
class TestDataset:
    def test_str(self):
        dataset = recipes.dataset.make(name='test dataset')
        assert str(dataset) == 'test dataset'

    def test_is_visible_to_user(self, user, other_user):
        dataset = recipes.dataset.make(author=user, name='mydataset', visibility="private")
        assert dataset.is_visible_to_user(user)
        assert not dataset.is_visible_to_user(other_user)

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
