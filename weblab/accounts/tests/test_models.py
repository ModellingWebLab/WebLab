import pytest

from accounts.models import User


@pytest.mark.django_db
def test_user_str():
    user = User.objects.create(
        username='testuser', email='test@example.com', full_name='Test User', institution='UCL'
    )
    assert str(user) == 'testuser (Test User)'
