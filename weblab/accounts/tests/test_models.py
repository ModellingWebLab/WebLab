import pytest
from django.core.exceptions import ValidationError

from accounts.models import User


@pytest.mark.django_db
def test_user_properties():
    user = User.objects.create(
        username='testuser',
        email='test@example.com',
        full_name='Test User',
        institution='UCL',
    )
    assert str(user) == 'testuser (Test User)'
    assert user.get_short_name() == 'testuser'
    assert user.get_full_name() == 'Test User'


@pytest.mark.django_db
def test_email_address_is_not_valid_username():
    """Since we can log in with either email address or username, we don't
    want to confuse the two"""
    with pytest.raises(ValidationError):
        User.objects.create(
            username='test@example.com',
            email='test@example.com',
            full_name='Test User',
            institution='UCL',
        ).full_clean()
