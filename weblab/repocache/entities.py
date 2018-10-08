from django.core.exceptions import ObjectDoesNotExist

from .exceptions import RepoCacheMiss
from .models import CachedEntity


def get_visibility(entity):
    try:
        return CachedEntity.objects.get(entity=entity).versions.latest().visibility
    except ObjectDoesNotExist:
        raise RepoCacheMiss()
