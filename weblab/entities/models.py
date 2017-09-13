from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator
from django.db import models


User = get_user_model()


class Entity(models.Model):
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_RESTRICTED = 'restricted'
    VISIBILITY_PUBLIC = 'public'

    VISIBILITY_CHOICES = (
        (VISIBILITY_PRIVATE, 'Private'),
        (VISIBILITY_RESTRICTED, 'Restricted'),
        (VISIBILITY_PUBLIC, 'Public')
    )

    name = models.CharField(validators=[MinLengthValidator(2)], max_length=255)
    creation_date = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User)
    visibility = models.CharField(
        max_length=16,
        choices=VISIBILITY_CHOICES,
        help_text=(
            'Public = anyone can view<br>'
            'Restricted = logged in users can view<br>'
            'Private = only you can view'
        ),
    )

    repository_url = models.URLField()

    class Meta:
        abstract = True


class ModelEntity(Entity):
    pass


class ProtocolEntity(Entity):
    pass
