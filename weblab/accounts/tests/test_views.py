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


@pytest.mark.django_db
def test_register(client, logged_in_user):
    assert not User.objects.filter(email='new@email.com').exists()

    # no password
    response = client.post('/accounts/register/', data={'email': 'new@email.com',
                                                        'institution': 'nottingham',
                                                        'full_name': 'john doe'})
    assert response.status_code == 200
    assert not User.objects.filter(email='new@email.com').exists()

    # passwords not matching
    response = client.post('/accounts/register/', data={'email': 'new@email.com',
                                                        'institution': 'nottingham',
                                                        'full_name': 'john doe',
                                                        'password1': 'h0rse_Battery_staple',
                                                        'password2': 'blabla'})
    assert response.status_code == 200
    assert not User.objects.filter(email='new@email.com').exists()

    # register successfully
    response = client.post('/accounts/register/', data={'email': 'new@email.com',
                                                        'institution': 'nottingham',
                                                        'full_name': 'john doe',
                                                        'password1': 'h0rse_Battery_staple',
                                                        'password2': 'h0rse_Battery_staple'})

    assert User.objects.filter(email='new@email.com').exists()
    assert response.status_code == 302


@pytest.mark.django_db
def test_edit_account(client, logged_in_user):
    assert logged_in_user.email != 'new@email.com'
    assert logged_in_user.institution != 'nottingham'
    assert not logged_in_user.receive_emails
    assert logged_in_user.receive_story_emails

    response = client.get('/accounts/myaccount/')
    assert response.status_code == 200

    response = client.post('/accounts/myaccount/', data={'email': 'new@email.com',
                                                         'institution': 'nottingham',
                                                         'receive_emails': 'on',
                                                         'receive_story_emails': ''})
    logged_in_user.refresh_from_db()
    assert logged_in_user.email == 'new@email.com'
    assert logged_in_user.institution == 'nottingham'
    assert logged_in_user.receive_emails
    assert not logged_in_user.receive_story_emails
    assert response.status_code == 302
