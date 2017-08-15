from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Allow authentication with either username or an email address.
    """
    def authenticate(self, username=None, password=None):
        field = 'email' if '@' in username else 'username'
        try:
            user = User.objects.get(**{field: username})
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
