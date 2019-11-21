from django.db.models import Q

from .models import CACHED_VERSION_TYPE_MAP, CachedModelVersion, CachedProtocolVersion


def get_public_entity_ids():
    """
    Get IDs of all entities with at least one publicly visible version

    :return: set of entity IDs
    """
    ids = set()
    for cls in (CachedModelVersion, CachedProtocolVersion):
        ids.update(
            cls.objects.filter(
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
    return ids


def get_moderated_entity_ids(entity_type=None):
    """
    Get IDs of all entities with at least one moderated version

    :return: set of entity IDs
    """
    entity_filter = Q(
        visibility='moderated',
    )
    if entity_type:
        classes = (CACHED_VERSION_TYPE_MAP[entity_type],)
    else:
        classes = (CachedModelVersion, CachedProtocolVersion)
    ids = set()
    for cls in classes:
        ids.update(
            cls.objects.filter(
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
    return ids
