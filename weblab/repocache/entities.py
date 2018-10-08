from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

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


def get_cached_version_visibility(entity, sha):
    """
    Get the visibility of a cached entity version

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


@transaction.atomic
def set_cached_version_visibility(entity, commit, visibility):
    """
    Set the visibility of a cached entity version, if it exists

    If the cached entity version does not exist, do nothing.

    :param entity: Entity object
    :param sha: hex string of the commit SHA of the version
    :param visibility: string representing visibility
    """
    objects = CachedEntityVersion.objects.filter(
        entity__entity=entity,
        sha=commit.hexsha,
    )

    if objects.exists():
        objects.update(visibility=visibility)
