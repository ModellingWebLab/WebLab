from django.db.models import F, Max, Q

from .models import CachedEntityVersion


def get_public_entity_ids():
    """
    Get IDs of all publicly visible entities

    :return: set of entity IDs
    """
    return set(
        CachedEntityVersion.objects.annotate(
            latest_ts=Max('entity__versions__timestamp')
        ).filter(
            timestamp=F('latest_ts'),
            visibility__in=['public', 'moderated'],
        ).values_list(
            'entity__entity_id', flat=True
        )
    )


def get_moderated_entity_ids(entity_type=None):
    """
    Get IDs of all moderated entities

    :return: set of entity IDs
    """

    entity_filter = Q(
        timestamp=F('latest_ts'),
        visibility='moderated',
    )

    if entity_type:
        entity_filter &= Q(entity__entity__entity_type=entity_type)

    return set(
        CachedEntityVersion.objects.annotate(
            latest_ts=Max('entity__versions__timestamp')
        ).filter(
            entity_filter,
        ).values_list(
            'entity__entity_id', flat=True
        )
    )
