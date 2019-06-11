import pytest
from django.db.utils import IntegrityError

from core import recipes
from datasets.models import ExperimentalDataset
from repocache.exceptions import RepoCacheMiss
from repocache.models import CachedEntity
from repocache.populate import populate_entity_cache


@pytest.mark.django_db
class TestDataset:
    def test_str(self):
        dataset = recipes.dataset.make(name='test dataset')
        assert str(dataset) == 'test dataset'

