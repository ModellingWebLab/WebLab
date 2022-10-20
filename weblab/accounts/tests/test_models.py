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
    assert user.is_staff ==False
    assert user.is_active == True
    assert user.get_short_name() == 'test@example.com'
    assert user.get_full_name() == 'Test User'
    assert user.receive_emails == False
    assert user.receive_story_emails  == True
    assert not user.is_superuser
