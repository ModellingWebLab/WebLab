import math
import os.path
from datetime import datetime

from django import template
from django.core.urlresolvers import reverse


register = template.Library()


@register.filter
def as_datetime(timestamp):
    return datetime.fromtimestamp(timestamp)


@register.filter
def number_of_files(commit):
    return len(commit.tree.blobs)


@register.filter
def human_readable_bytes(num_bytes):
    sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
    if not num_bytes:
        return '0 Bytes'
    i = int(math.log(num_bytes, 1024))
    return '{:.2f} {}'.format(num_bytes / (1024**i), sizes[i])


@register.filter
def file_type(filename):
    _, ext = os.path.splitext(filename)

    extensions = {
        'cellml': 'CellML',
        'txt': 'TXTPROTOCOL',
        'xml': 'XMLPROTOCOL',
        'zip': 'COMBINE archive',
        'omex': 'COMBINE archive',
    }

    return extensions.get(ext[1:], 'Unknown')


@register.filter
def url_versions(entity):
    url_name = 'entities:{}_versions'.format(entity.entity_type)
    return reverse(url_name, args=[entity.id])


@register.filter
def url_newversion(entity):
    url_name = 'entities:{}_newversion'.format(entity.entity_type)
    return reverse(url_name, args=[entity.id])


@register.filter
def url_version(entity, commit):
    url_name = 'entities:{}_version'.format(entity.entity_type)
    tags = entity.tag_dict
    args = [entity.id, tags.get(commit, [commit.hexsha])[-1]]
    return reverse(url_name, args=args)


@register.filter
def url_entity(entity):
    url_name = 'entities:{}'.format(entity.entity_type)
    return reverse(url_name, args=[entity.id])


@register.filter
def url_new(entity_type):
    url_name = 'entities:new_{}'.format(entity_type)
    return reverse(url_name)


@register.simple_tag(takes_context=True)
def can_create_version(context, entity_type):
    user = context['user']
    return user.has_perm('entities.create_{}_version'.format(entity_type))


@register.simple_tag(takes_context=True)
def can_create_entity(context, entity_type):
    user = context['user']
    return user.has_perm('entities.create_{}'.format(entity_type))
