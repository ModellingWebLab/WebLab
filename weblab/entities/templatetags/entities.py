import math
import os.path

from django import template
from django.core.urlresolvers import reverse


register = template.Library()


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
    return reverse('entities:version_list', args=[entity.entity_type, entity.id])


@register.filter
def url_newversion(entity):
    return reverse('entities:newversion', args=[entity.entity_type, entity.id])


@register.filter
def url_tag_version(entity, version):
    return reverse('entities:tag_version', args=[entity.id, version.hexsha])


@register.filter
def url_entity_comparison_json(entity_versions, entity_type):
    """
    Build URL for entity comparison json
    """
    if entity_versions:
        version_ids = '/' + '/'.join(entity_versions)
    else:
        version_ids = ''
    return reverse('entities:compare_json', args=[entity_type, version_ids])


@register.simple_tag
def url_entity_comparison_base(entity_type):
    """
    Base URL for entity comparison page
    """
    # Use dummy IDs to set up a comparison URL, then chop them off to
    # get the base. This will be used by javascript to generate comparisons
    # between experiment versions.
    url = reverse('entities:compare', args=[entity_type, '/1:a'])
    return url[:-4]


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
    last_tag = str(entity.repo.tag_dict.get(commit.hexsha, ['/'])[-1])
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
    url_name = 'entities:version'
    last_tag = _url_friendly_label(entity, commit)
    args = [entity.entity_type, entity.id, last_tag]
    return reverse('entities:version', args=args)


@register.filter
def url_version_json(entity, commit):
    """
    Generate the json URL for a specific version of this entity.
    """
    url_name = 'entities:version_json'
    last_tag = _url_friendly_label(entity, commit)
    args = [entity.entity_type, entity.id, last_tag]
    return reverse(url_name, args=args)


@register.filter
def url_compare_experiments(entity, commit):
    """Generate the view URL for comparing experiments using
    a specific version of this entity

    e.g. comparing experiments using version of a model across all available protocols
    """
    url_name = 'entities:compare_experiments'
    last_tag = _url_friendly_label(entity, commit)
    args = [entity.entity_type, entity.id, last_tag]
    return reverse(url_name, args=args)


@register.filter
def url_change_version_visibility(entity, commit):
    last_tag = _url_friendly_label(entity, commit)
    args = [entity.entity_type, entity.id, last_tag]
    return reverse('entities:change_visibility', args=args)


@register.filter
def url_entity(entity):
    url_name = 'entities:detail'
    return reverse(url_name, args=[entity.entity_type, entity.id])


@register.filter
def url_new(entity_type):
    return reverse('entities:new', args=[entity_type])


@register.filter
def url_delete(entity):
    url_name = 'entities:delete'
    return reverse(url_name, args=[entity.entity_type, entity.id])


@register.filter
def url_collaborators(entity):
    url_name = 'entities:entity_collaborators'
    return reverse(url_name, args=[entity.entity_type, entity.id])


@register.simple_tag(takes_context=True)
def can_create_version(context, entity):
    return entity.is_editable_by(context['user'])


@register.simple_tag(takes_context=True)
def can_create_entity(context, entity_type):
    user = context['user']
    return user.has_perm('entities.create_{}'.format(entity_type))


@register.simple_tag(takes_context=True)
def can_delete_entity(context, entity):
    user = context['user']
    return entity.is_deletable_by(user)

@register.simple_tag(takes_context=True)
def can_manage_entity(context, entity):
    user = context['user']
    return entity.is_managed_by(user)
