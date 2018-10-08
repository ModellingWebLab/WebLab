from django.core.exceptions import ObjectDoesNotExist

from .exceptions import RepoCacheMiss
from .models import CachedEntity, CachedEntityVersion


def get_visibility(entity):
    """
    Get the visibility of an entity

    :param entity: Entity object
    :return: string representing visibility
    :raise: RepoCacheMiss if entity does not exist in cache, or has no versions
    """
    try:
        return CachedEntity.objects.get(entity=entity).versions.latest().visibility
    except ObjectDoesNotExist:
        raise RepoCacheMiss("Entity not found or has no commits")


def get_version_visibility(entity, sha):
    """
    Get the visibility of a version of an entity

    :param entity: Entity object
    :param sha: hex string of the commit SHA of the version

    :return: string representing visibility
    :raise: RepoCacheMiss if entity does not exist in cache, or has no versions
    """
    try:
        return CachedEntityVersion.objects.get(
            entity__entity=entity,
            sha=sha
        ).visibility
    except ObjectDoesNotExist:
        raise RepoCacheMiss("Entity version not found")
