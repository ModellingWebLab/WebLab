# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-11-20 11:56
from __future__ import unicode_literals

from django.db import migrations


def split_cache(apps, schema_editor):
    """Split a generic entity repocache into entity-type-specific cache tables.

    Based on the Entity.entity_type field, this will split the CachedEntity, CachedEntityVersion
    and CachedEntityTag caches in Model- and Protocol-specific versions.
    """
    CachedEntity = apps.get_model('repocache', 'CachedEntity')
    CachedEntityVersion = apps.get_model('repocache', 'CachedEntityVersion')
    CachedEntityTag = apps.get_model('repocache', 'CachedEntityTag')

    CachedModel = apps.get_model('repocache', 'CachedModel')
    CachedModelVersion = apps.get_model('repocache', 'CachedModelVersion')
    CachedModelTag = apps.get_model('repocache', 'CachedModelTag')

    CachedProtocol = apps.get_model('repocache', 'CachedProtocol')
    CachedProtocolVersion = apps.get_model('repocache', 'CachedProtocolVersion')
    CachedProtocolTag = apps.get_model('repocache', 'CachedProtocolTag')

    ProtocolInterface = apps.get_model('repocache', 'ProtocolInterface')

    for cached_entity in CachedEntity.objects.all():
        if cached_entity.entity.entity_type == 'model':
            new_cls = CachedModel
            new_version_cls = CachedModelVersion
            new_tag_cls = CachedModelTag
        else:
            new_cls = CachedProtocol
            new_version_cls = CachedProtocolVersion
            new_tag_cls = CachedProtocolTag
        new_cached_entity = new_cls(entity=cached_entity.entity)
        new_cached_entity.save()

        for cached_version in cached_entity.versions.all():
            new_cached_version = new_version_cls(
                entity=new_cached_entity,
                visibility=cached_version.visibility,
                sha=cached_version.sha,
                timestamp=cached_version.timestamp,
                parsed_ok=cached_version.parsed_ok,
            )
            new_cached_version.save()

            for cached_tag in cached_version.tags.all():
                new_cached_tag = new_tag_cls(
                    entity=new_cached_entity,
                    tag=cached_tag.tag,
                    version=new_cached_version,
                )
                new_cached_tag.save()

    # Transfer protocol interface terms from the generic to protocol-specific caches
    for iface in ProtocolInterface.objects.all():
        old_cache_version = iface.protocol_version
        protocol = old_cache_version.entity.entity
        iface.new_protocol_version = CachedProtocolVersion.objects.get(
            sha=old_cache_version.sha,
            entity=CachedProtocol.objects.get(entity__pk=protocol.pk)
        )
        iface.save()

    # Remove old generic cache entries, so reverse migration doesn't duplicate data
    CachedEntity.objects.all().delete()


def combine_caches(apps, schema_editor):
    """Combine entity-type-specific cache tables into a generic repocache.

    This will fill the CachedEntity, CachedEntityVersion and CachedEntityTag caches
    from Model- and Protocol-specific versions.
    """
    CachedEntity = apps.get_model('repocache', 'CachedEntity')
    CachedEntityVersion = apps.get_model('repocache', 'CachedEntityVersion')
    CachedEntityTag = apps.get_model('repocache', 'CachedEntityTag')

    CachedModel = apps.get_model('repocache', 'CachedModel')
    CachedModelVersion = apps.get_model('repocache', 'CachedModelVersion')
    CachedModelTag = apps.get_model('repocache', 'CachedModelTag')

    CachedProtocol = apps.get_model('repocache', 'CachedProtocol')
    CachedProtocolVersion = apps.get_model('repocache', 'CachedProtocolVersion')
    CachedProtocolTag = apps.get_model('repocache', 'CachedProtocolTag')

    ProtocolInterface = apps.get_model('repocache', 'ProtocolInterface')

    for cache_type in ((CachedModel, CachedModelVersion, CachedModelTag),
                       (CachedProtocol, CachedProtocolVersion, CachedProtocolTag)):
        entity_cls, version_cls, tag_cls = cache_type
        for cached_entity in entity_cls.objects.all():
            new_cached_entity = CachedEntity(entity=cached_entity.entity)
            new_cached_entity.save()

            for cached_version in cached_entity.versions.all():
                new_cached_version = CachedEntityVersion(
                    entity=new_cached_entity,
                    visibility=cached_version.visibility,
                    sha=cached_version.sha,
                    timestamp=cached_version.timestamp,
                    parsed_ok=cached_version.parsed_ok,
                )
                new_cached_version.save()

                for cached_tag in cached_version.tags.all():
                    new_cached_tag = CachedEntityTag(
                        entity=new_cached_entity,
                        tag=cached_tag.tag,
                        version=new_cached_version,
                    )
                    new_cached_tag.save()

    # Transfer protocol interface terms from the protocol-specific to generic caches
    for iface in ProtocolInterface.objects.all():
        new_cache_version = iface.new_protocol_version
        protocol = new_cache_version.entity.entity
        iface.protocol_version = CachedEntityVersion.objects.get(
            sha=new_cache_version.sha,
            entity=CachedEntity.objects.get(entity__pk=protocol.pk)
        )
        iface.save()

    # Remove old specific cache entries, so repeat forward migration doesn't duplicate data
    CachedModel.objects.all().delete()
    CachedProtocol.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('repocache', '0011_auto_20191120_1143'),
    ]

    operations = [
        migrations.RunPython(split_cache, combine_caches),
    ]
