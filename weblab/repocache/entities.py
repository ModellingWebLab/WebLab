from django.db.models import Max

from .models import CachedEntityVersion


def get_public_entity_ids():
    """
    Get IDs of all publicly visible entities

    :return: set of entity IDs
    """
    return {
        val['entity__entity_id']
        for val in (CachedEntityVersion.objects.values(
            'entity__entity_id')
            .filter(visibility='public')
            .annotate(Max('timestamp'))
            .order_by('-timestamp'))
    }


def get_restricted_entity_ids():
    """
    Get IDs of all entities with restricted visibility

    :return: set of entity IDs
    """
    return {
        val['entity__entity_id']
        for val in (CachedEntityVersion.objects.values(
            'entity__entity_id')
            .filter(visibility='restricted')
            .annotate(Max('timestamp'))
            .order_by('-timestamp'))
    }
