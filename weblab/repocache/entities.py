from django.db.models import F, Max

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
            visibility='public',
        ).values_list(
            'entity__entity_id', flat=True
        )
    )
