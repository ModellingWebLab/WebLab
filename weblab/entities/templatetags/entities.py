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
def url_tag_version(entity, version):
    url_name = 'entities:tag_version'
    return reverse(url_name, args=[entity.id, version.hexsha])


@register.filter
def name_of_model(experiment):
    model = experiment.model
    model_version = model.repo.get_name_for_commit(experiment.model_version)
    return '%s @ %s' % (model.name, model_version)


@register.filter
def name_of_protocol(experiment):
    protocol = experiment.protocol
    protocol_version = protocol.repo.get_name_for_commit(experiment.protocol_version)
    return '%s @ %s' % (protocol.name, protocol_version)


def _url_friendly_label(entity, commit):
    """
    Get URL-friendly version label for a commit

    :param entity: Entity the commit belongs to
    :param commit: `git.Commit` object
    """
    last_tag = str(entity.repo.tag_dict.get(commit, ['/'])[-1])
    if '/' in last_tag or last_tag in ['new', 'latest']:
        last_tag = commit.hexsha
    return last_tag


@register.filter
def url_version(entity, commit):
    """Generate the view URL for a specific version of this entity.

    We try to use the last tag name in the URL, but if there isn't
    a tag, or the tag contains a /, or the tag is one of our reserved
    names (new, latest), we fall back to the SHA1.
    """
    url_name = 'entities:{}_version'.format(entity.entity_type)
    last_tag = _url_friendly_label(entity, commit)
    args = [entity.id, last_tag]
    return reverse(url_name, args=args)


@register.filter
def url_version_json(entity, commit):
    """
    Generate the json URL for a specific version of this entity.
    """
    url_name = 'entities:{}_version_json'.format(entity.entity_type)
    last_tag = _url_friendly_label(entity, commit)
    args = [entity.id, last_tag]
    return reverse(url_name, args=args)


@register.filter
def url_version_compare(entity, commit):
    """Generate the view URL for comparing a specific version of this entity
    to entities of the other type.

    e.g. comparing a version of a model to the available set of protocols
    """
    url_name = 'entities:{}_version_compare'.format(entity.entity_type)
    last_tag = _url_friendly_label(entity, commit)
    args = [entity.id, last_tag]
    return reverse(url_name, args=args)


@register.filter
def url_entity(entity):
    url_name = 'entities:{}'.format(entity.entity_type)
    return reverse(url_name, args=[entity.id])


@register.filter
def url_new(entity_type):
    url_name = 'entities:new_{}'.format(entity_type)
    return reverse(url_name)


@register.filter
def url_delete(entity):
    url_name = 'entities:{}_delete'.format(entity.entity_type)
    return reverse(url_name, args=[entity.id])


@register.simple_tag(takes_context=True)
def can_create_version(context, entity_type):
    user = context['user']
    return user.has_perm('entities.create_{}_version'.format(entity_type))


@register.simple_tag(takes_context=True)
def can_create_entity(context, entity_type):
    user = context['user']
    return user.has_perm('entities.create_{}'.format(entity_type))


@register.simple_tag(takes_context=True)
def can_delete_entity(context, entity):
    user = context['user']
    return entity.is_deletable_by(user)
