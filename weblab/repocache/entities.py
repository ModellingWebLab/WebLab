from django.db.models import Q

from .models import CachedEntityVersion


def get_public_entity_ids():
    """
    Get IDs of all entities with at least one publicly visible version

    :return: set of entity IDs
    """
    return set(
        CachedEntityVersion.objects.filter(
            visibility__in=['public', 'moderated'],
        ).order_by(
            'entity__id',
            '-timestamp',
            '-pk',
        ).distinct(
            'entity__id',
        ).values_list(
            'entity__entity_id', flat=True
        )
    )


def get_moderated_entity_ids(entity_type=None):
    """
    Get IDs of all entities with at least one moderated version

    :return: set of entity IDs
    """

    entity_filter = Q(
        visibility='moderated',
    )

    if entity_type:
        entity_filter &= Q(entity__entity__entity_type=entity_type)

    return set(
        CachedEntityVersion.objects.filter(
            entity_filter,
        ).order_by(
            'entity__id',
            '-timestamp',
            '-pk',
        ).distinct(
            'entity__id',
        ).values_list(
            'entity__entity_id', flat=True
        )
    )
