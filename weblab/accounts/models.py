from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(PermissionsMixin, AbstractBaseUser):
    username = models.CharField(
        max_length=255,
        unique=True,
        validators=[UnicodeUsernameValidator()],
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

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'full_name', 'institution']

    objects = UserManager()

    def __str__(self):
        return '%s (%s)' % (self.username, self.full_name)

    def get_short_name(self):
        return self.username

    def get_full_name(self):
        return self.full_name
