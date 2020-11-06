import pytest
from django.core import mail

from accounts.models import User
from core import recipes
from datasets.models import Dataset


@pytest.fixture
def superuser():
    return User.objects.create(
        email='admin@example.com',
        full_name='Admin User',
        is_superuser=True
    )


@pytest.mark.django_db
def test_email_sent_on_user_creation(superuser):
    assert len(mail.outbox) == 0
    user = User.objects.create(
        email='test@example.com',
        full_name='Test User',
    )
    assert len(mail.outbox) == 1
    body = mail.outbox[0].body
    assert 'Test User' in body
    assert 'test@example.com' in body
    assert 'http://127.0.0.1:8000/admin/accounts/user/{}/change/'.format(user.pk) in body


@pytest.mark.django_db
def test_delete_user_directory(client, logged_in_user, my_dataset):
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
