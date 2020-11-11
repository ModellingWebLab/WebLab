from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_save, pre_delete

from .signals import user_created, user_deleted


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        # When the app is ready, connect up signals
        post_save.connect(user_created, sender=settings.AUTH_USER_MODEL)
        pre_delete.connect(user_deleted, sender=settings.AUTH_USER_MODEL)
