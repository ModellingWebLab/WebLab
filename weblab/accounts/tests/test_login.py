import pytest
from accounts.models import User


@pytest.fixture
def valid_user():
    return User.objects.create_user(
        email='test@example.com',
        full_name='Test User',
        institution='UCL',
        password='password',
    )


@pytest.mark.django_db
def test_login_with_email(client, valid_user):
    assert client.login(username=valid_user.email, password='password')
