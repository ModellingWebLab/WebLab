import pytest

import datasets.templatetags.datasets as dataset_tags
from datasets.models import ExperimentalDataset

from core import recipes


# @pytest.mark.django_db
# def test_dataset_urls_no_files(dataset_no_files):
#     dataset = dataset_no_files
#     assert dataset_tags.url_dataset(dataset) == '/datasets/%d/addfiles' % dataset.pk


# @pytest.mark.django_db
# def test_dataset_urls_with_files(dataset_dummy_files):
#     dataset = dataset_dummy_files
#     assert dataset_tags.url_dataset(dataset) == '/datasets/%d' % dataset.pk
#
#
@pytest.mark.django_db
def test_can_create_dataset_no_permission(user, helpers):
    context = {'user': user}
    assert not dataset_tags.can_create_dataset(context)


@pytest.mark.django_db
def test_can_create_dataset_permission(dataset_creator):
    context = {'user': dataset_creator}
    assert dataset_tags.can_create_dataset(context)


