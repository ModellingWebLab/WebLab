import pytest

from datasets.forms import DatasetColumnMappingFormSet


@pytest.mark.django_db
class TestDatasetColumnMappingFormSet:
    def test_has_formset(self, public_dataset):
        formset = DatasetColumnMappingFormSet(instance=public_dataset)
        assert formset.instance == public_dataset
