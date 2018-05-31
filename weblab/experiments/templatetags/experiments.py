from django import template
from django.core.urlresolvers import reverse


register = template.Library()


@register.filter
def url_comparison(experiment_versions):
    version_ids = '/' + '/'.join(str(ver.id) for ver in experiment_versions)
    return reverse('experiments:compare_json', args=[version_ids])
