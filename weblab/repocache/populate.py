from django.db import transaction

from .models import get_or_create_cached_entity


@transaction.atomic
def populate_entity_cache(entity):
    """
    Process the repository of the given entity, adding the relevant cache entries,
    according to entity type.

    :param entity: entity to process
    """
    cached, cache_created = get_or_create_cached_entity(entity)

    tag_dict = entity.repo.tag_dict

    visibility = entity.DEFAULT_VISIBILITY
    commits_without_visibility = []
    valid_shas = set()
    for commit in entity.repo.commits:
        valid_shas.add(commit.sha)
        visibility = entity.get_visibility_from_repo(commit)
        version = cached.CachedVersionClass.objects.get_or_create(
            entity=cached,
            sha=commit.sha,
            defaults={
                'timestamp': commit.timestamp,
                'message': commit.message,
                'master_filename': commit.master_filename,
                'visibility': visibility or entity.DEFAULT_VISIBILITY,
            }
        )[0]
        # Check if any updates are needed to an already-present cached version
        if commit.message != version.message:
            version.message = commit.message
            version.save()
        if commit.master_filename != version.master_filename:
            version.master_filename = commit.master_filename
            version.save()
        if visibility and visibility != version.visibility:
            version.visibility = visibility
            version.save()

        # If the commit has no visibility info in the repo, remember this
        # and wait until we find visibility on an earlier commit (which
        # will be encountered later since we are iterating backwards through
        # commits)
        if visibility:
            # Apply this commit's visibility to all those later (previously
            # encountered) commits which have no visibility info
            for sha in commits_without_visibility:
                entity.set_version_visibility(sha, visibility)
            commits_without_visibility = []
        else:
            commits_without_visibility.append(commit.sha)

        cached.versions.add(version)

        # Store any tags related to this commit
        for tag in tag_dict.get(commit.sha, []):
            cached.tags.add(
                cached.CachedTagClass.objects.get_or_create(
                    entity=cached,
                    tag=tag.name,
                    defaults={'version': version},
                )[0])

    # Purge cache of stale entries, if any
    if not cache_created:
        for cached_version in cached.versions.all():
            if cached_version.sha not in valid_shas:
                cached_version.delete()
        for cached_tag in cached.tags.all().select_related('version'):
            if cached_tag.version.sha not in tag_dict:
                cached_tag.delete()
