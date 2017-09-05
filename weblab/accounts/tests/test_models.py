import pytest

from accounts.models import User


@pytest.mark.django_db
def test_user_properties():
    user = User.objects.create(
        email='test@example.com',
        full_name='Test User',
        institution='UCL',
    )
    assert str(user) == 'test@example.com (Test User)'
    assert user.get_short_name() == 'test@example.com'
    assert user.get_full_name() == 'Test User'
