import pytest
from django.urls import reverse

from accounts.models import User
from core import recipes
from datasets.models import Dataset


def test_my_account_view_requires_login(client):
    response = client.get('/accounts/myaccount/')
    assert response.status_code == 302
    assert '/login/' in response.url


@pytest.mark.django_db
def test_user_can_delete_own_account(client, logged_in_user, my_dataset):
    recipes.model.make(author=logged_in_user)
    dataset = my_dataset
    user_directory_repo = logged_in_user.get_storage_dir('repo')
    user_directory_dataset = logged_in_user.get_storage_dir('dataset')
    assert Dataset.objects.filter(pk=dataset.pk).exists()

    assert user_directory_repo.is_dir()
    assert user_directory_dataset.is_dir()

    response = client.post(
        '/accounts/%d/delete/' % logged_in_user.pk,
    )

    assert response.status_code == 302
    assert not User.objects.filter(pk=logged_in_user.pk).exists()
    assert not user_directory_repo.exists()
    assert not Dataset.objects.filter(pk=dataset.pk).exists()
    assert not user_directory_dataset.exists()
    assert response.url == reverse('home')


@pytest.mark.django_db
def test_delete_user_requires_login(client, other_user):
    recipes.model.make(author=other_user)
    user_directory_repo = other_user.get_storage_dir('repo')
    assert user_directory_repo.is_dir()
    response = client.post(
        '/accounts/%d/delete/' % other_user.pk,
    )
    assert response.status_code == 302
    assert User.objects.filter(pk=other_user.pk).exists()
    assert user_directory_repo.exists()
    assert '/login' in response.url


@pytest.mark.django_db
def test_cannot_delete_other_account(client, logged_in_user, other_user):
    recipes.model.make(author=other_user)
    user_directory_repo = other_user.get_storage_dir('repo')

    assert user_directory_repo.is_dir()

    response = client.post(
        '/accounts/%d/delete/' % other_user.pk,
    )

    assert response.status_code == 403
    assert User.objects.filter(pk=other_user.pk).exists()
    assert user_directory_repo.exists()
