from html import escape

from django import template
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe


register = template.Library()


@register.filter
def url_experiment_comparison_json(experiment_versions):
    """
    Build URL for experiment comparison json
    """
    if experiment_versions:
        version_ids = '/' + '/'.join(str(ver.id) for ver in experiment_versions)
    else:
        version_ids = ''
    return reverse('experiments:compare_json', args=[version_ids])


@register.simple_tag
def url_experiment_comparison_base():
    """
    Base URL for experiment comparison page
    """
    # Use dummy IDs to set up a comparison URL, then chop them off to
    # get the base. This will be used by javascript to generate comparisons
    # between experiment versions.
    url = reverse('experiments:compare', args=['/1/1'])
    return url[:-4]


@register.simple_tag(takes_context=True)
def dataset_options(context, experiment):
    html = ''
    for dataset in experiment.protocol.protocol_experimental_datasets.visible_to_user(context['user']):
        html += ('<option value="' +
                 reverse('datasets:version_json', args=(dataset.id,)) + '">' + escape(dataset.name) + '</option>')

    return mark_safe(html)


@register.filter
def url_version_comparison_matrix(entity):
    """
    Build URL for submatrix view
    """
    kwargs = {}
    if entity.entity_type == 'model':
        kwargs['model_pks'] = '/%d' % entity.pk
        kwargs['model_versions'] = '/*'
    elif entity.entity_type == 'protocol':
        kwargs['protocol_pks'] = '/%d' % entity.pk
        kwargs['protocol_versions'] = '/*'

    return reverse('experiments:list', kwargs=kwargs)


@register.simple_tag(takes_context=True)
def can_delete_entity(context, entity):
    user = context['user']
    return entity.is_deletable_by(user)
