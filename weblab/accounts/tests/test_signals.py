import pytest
from django.core import mail

from accounts.models import User


@pytest.fixture
def superuser():
    return User.objects.create(
        email='admin@example.com',
        full_name='Admin User',
        is_superuser=True
    )


@pytest.mark.django_db
def test_user_created_called_on_user_creation(superuser):
    assert len(mail.outbox) == 0
    User.objects.create(
        email='test@example.com',
        full_name='Test User',
    )
    assert len(mail.outbox) == 1
