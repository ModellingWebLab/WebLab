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
