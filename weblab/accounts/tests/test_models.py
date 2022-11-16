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
    assert not user.is_staff
    assert user.is_active
    assert user.get_short_name() == 'test@example.com'
    assert user.get_full_name() == 'Test User'
    assert not user.receive_emails
    assert user.receive_story_emails
    assert not user.is_superuser
