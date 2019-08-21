import pytest

import datasets.templatetags.datasets as dataset_tags


@pytest.mark.django_db
def test_dataset_urls_no_files(my_dataset):
    assert dataset_tags.url_dataset(my_dataset) == '/datasets/%d/addfiles' % my_dataset.pk


@pytest.mark.django_db
def test_can_create_dataset_no_permission(user):
    context = {'user': user}
    assert not dataset_tags.can_create_dataset(context)


@pytest.mark.django_db
def test_can_create_dataset_permission(dataset_creator):
    context = {'user': dataset_creator}
    assert dataset_tags.can_create_dataset(context)
