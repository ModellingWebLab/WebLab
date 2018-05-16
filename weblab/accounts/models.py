from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(PermissionsMixin, AbstractBaseUser):
    email = models.EmailField(
        unique=True,
        error_messages={
            'unique': "A user with that email address already exists.",
        },
    )

    full_name = models.CharField(max_length=255)
    institution = models.CharField(max_length=255, blank=True)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)

    receive_emails = models.BooleanField(
        default=False,
        help_text='User wants to receive emails',
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'institution']

    objects = UserManager()

    def __str__(self):
        return '%s (%s)' % (self.email, self.full_name)

    def get_short_name(self):
        return self.email

    def get_full_name(self):
        return self.full_name
