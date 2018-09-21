from django.db import transaction

from .models import CachedEntity, CachedEntityTag, CachedEntityVersion


@transaction.atomic
def index_entity_repo(entity):
    """
    Process the repository of the given entity,
    adding CachedEntity and related models

    :param entity: entity to process
    """
    # The delete will cascade to versions and tags
    CachedEntity.objects.filter(entity=entity).delete()

    cached = CachedEntity.objects.create(
        entity=entity,
        latest_version=None
    )

    tag_dict = entity.repo.tag_dict

    for commit in entity.repo.commits:
        version = CachedEntityVersion.objects.create(
            entity=cached,
            sha=commit.hexsha,
            visibility=entity.get_version_visibility(commit.hexsha),
        )
        cached.versions.add(version)

        # Store the first version we encounter as "latest" for the repo.
        if not cached.latest_version:
            cached.latest_version = version
            cached.save()

        # Store any tags pertaining to this commit
        for tag in tag_dict.get(commit.hexsha, []):
            cached.tags.add(
                CachedEntityTag.objects.create(
                    entity=cached,
                    tag=tag.name,
                    version=version
                ))
