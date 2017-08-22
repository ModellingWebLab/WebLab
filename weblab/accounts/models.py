from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core import validators
from django.db import models
from django.utils import timezone
from django.utils.deconstruct import deconstructible

from .managers import UserManager


@deconstructible
class UsernameValidator(validators.RegexValidator):
    """
    Custom validator for usernames - this is similar to Django builtin validator
    but prevents registration of usernames with '@' - we want this because
    email addresses can be used to log in, and we don't want to cause
    confusion or ambiguity in the authentication system.
    """
    regex = r'^[\w.+-]+$'
    message = (
        'Enter a valid username. This value may contain only letters, '
        'numbers, and ./+/-/_ characters.'
    )


class User(PermissionsMixin, AbstractBaseUser):
    username = models.CharField(
        max_length=255,
        unique=True,
        validators=[UsernameValidator()],
        error_messages={
            'unique': "A user with that username already exists.",
        },
    )

    email = models.EmailField(
        unique=True,
        error_messages={
            'unique': "A user with that email address already exists.",
        },
    )

    full_name = models.CharField(max_length=255)
    institution = models.CharField(max_length=255)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)

    receive_emails = models.BooleanField(
        default=False,
        help_text='User wants to receive emails',
    )

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'full_name', 'institution']

    objects = UserManager()

    def __str__(self):
        return '%s (%s)' % (self.username, self.full_name)

    def get_short_name(self):
        return self.username

    def get_full_name(self):
        return self.full_name
