from django.db import transaction

from core.visibility import Visibility

from .models import CachedEntity, CachedEntityTag, CachedEntityVersion


@transaction.atomic
def populate_entity_cache(entity):
    """
    Process the repository of the given entity,
    adding CachedEntity and related models

    :param entity: entity to process
    """
    # The delete will cascade to versions and tags
    CachedEntity.objects.filter(entity=entity).delete()

    cached = CachedEntity.objects.create(entity=entity)

    tag_dict = entity.repo.tag_dict

    visibility = 'private'
    commits_without_visibility = []
    for commit in entity.repo.commits:
        visibility = entity.get_visibility_from_repo(commit)
        version = CachedEntityVersion.objects.create(
            entity=cached,
            sha=commit.hexsha,
            timestamp=commit.committed_at,
            visibility=visibility or Visibility.PRIVATE
        )

        # If the commit has no visibility info in the repo. remember this
        # and wait until we find visibility on an earlier commit (which
        # will be encountered later since we are iterating backwards through
        # commits)
        if visibility:
            # Apply this commit's visibility to all those later (previously
            # encountered) commits which have no visibility info
            for sha in commits_without_visibility:
                entity.set_version_visibility(sha, visibility)
        else:
            commits_without_visibility.append(commit.hexsha)

        cached.versions.add(version)

        # Store any tags related to this commit
        for tag in tag_dict.get(commit.hexsha, []):
            cached.tags.add(
                CachedEntityTag.objects.create(
                    entity=cached,
                    tag=tag.name,
                    version=version
                ))
