import math

from django import template
from django.core.urlresolvers import reverse

from core.filetypes import get_file_type


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
    return get_file_type(filename)


@register.simple_tag(takes_context=True)
def ns_url(context, name, *args):
    """An extended version of the built-in url tag that dynamically figures out the namespace portion.

    :param name: the URL pattern name, *without* initial namespace (that will be determined from context)
    :param args: any positional args for the URL
    """
    ns = context['current_namespace']
    return reverse(ns + ':' + name, args=args)


@register.simple_tag(takes_context=True)
def entity_url(context, name, entity, *args):
    """An extended version of the built-in url tag specifically for common entity URLs.

    :param name: the URL pattern name, *without* initial namespace (that will be determined from context)
    :param entity: the entity this URL is about
    :param args: any extra positional args for the URL
    """
    ns = context['current_namespace']
    return reverse(ns + ':' + name, args=(entity.url_type, entity.id) + args)


@register.simple_tag(takes_context=True)
def entity_version_url(context, name, entity, commit, *args):
    """An extended version of the built-in url tag specifically for common entity version URLs.

    :param name: the URL pattern name, *without* initial namespace (that will be determined from context)
    :param entity: the entity this URL is about
    :param commit: the version this URL is about
    :param args: any extra positional args for the URL
    """
    ns = context['current_namespace']
    url_name = ns + ':' + name
    last_tag = _url_friendly_label(entity, commit)
    args = (entity.url_type, entity.id, last_tag) + args
    return reverse(url_name, args=args)


@register.simple_tag(takes_context=True)
def tag_version_url(context, entity, commit):
    """Generate the URL for tagging a version of an entity.

    :param entity: the entity this URL is about
    :param commit: the version this URL is about
    """
    ns = context['current_namespace']
    url_name = ns + ':tag_version'
    last_tag = _url_friendly_label(entity, commit)
    args = (entity.id, last_tag)
    return reverse(url_name, args=args)


@register.simple_tag(takes_context=True)
def entity_comparison_json_url(context, entity_versions, entity_type):
    """Generate a URL for the EntityComparisonJsonView."""
    ns = context['current_namespace']
    if entity_versions:
        version_ids = '/' + '/'.join(entity_versions)
    else:
        version_ids = ''
    return reverse(ns + ':compare_json', args=[entity_type, version_ids])


@register.simple_tag(takes_context=True)
def url_entity_comparison_base(context, entity_type):
    """
    Base URL for entity comparison page
    """
    # Use dummy IDs to set up a comparison URL, then chop them off to
    # get the base. This will be used by javascript to generate comparisons
    # between entity versions.
    ns = context['current_namespace']
    url = reverse(ns + ':compare', args=[entity_type, '/1:a'])
    return url[:-4]


@register.simple_tag(takes_context=True)
def url_entity_diff_base(context, entity_type):
    """
    Base URL for entity diff
    """
    # Use dummy IDs to set up a diff URL, then chop them off to
    # get the base. This will be used by javascript to generate diff URLs
    # between entity versions.
    ns = context['current_namespace']
    url = reverse(ns + ':diff', args=[entity_type, '/1:a/2:b', 'file.json'])
    return url.split('/1:a/2:b')[0]


@register.filter
def name_of_model(experiment):
    model = experiment.model
    model_version = model.repocache.get_name_for_version(experiment.model_version.sha)
    return '%s @ %s' % (model.name, model_version)


@register.filter
def name_of_protocol(experiment):
    protocol = experiment.protocol
    protocol_version = protocol.repocache.get_name_for_version(experiment.protocol_version.sha)
    return '%s @ %s' % (protocol.name, protocol_version)


def _url_friendly_label(entity, version):
    """
    Get URL-friendly version label for a commit

    :param entity: Entity the commit belongs to
    :param version: CachedEntityVersion object
    """
    tags = version.tags.last()
    if tags is not None:
        tag = tags.tag
        if tag is None or tag in ['new', 'latest']:
            return version.sha
        else:
            return tag
    return version.sha


@register.filter
def url_compare_experiments(entity, commit):
    """Generate the view URL for comparing experiments using
    a specific version of this entity

    e.g. comparing experiments using version of a model across all available protocols
    """
    url_name = 'entities:compare_experiments'
    last_tag = _url_friendly_label(entity, commit)
    args = [entity.url_type, entity.id, last_tag]
    return reverse(url_name, args=args)


@register.filter
def url_run_experiments(entity, commit):
    last_tag = _url_friendly_label(entity, commit)
    args = [entity.url_type, entity.id, last_tag]
    return reverse('entities:runexperiments', args=args)


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
