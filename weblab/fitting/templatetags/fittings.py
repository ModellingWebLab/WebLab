from django import template
from django.core.urlresolvers import reverse


register = template.Library()


@register.simple_tag
def url_fitting_comparison_base():
    """
    Base URL for fitting result comparison page
    """
    # Use dummy IDs to set up a comparison URL, then chop them off to
    # get the base. This will be used by javascript to generate comparisons
    # between fitting result versions.
    url = reverse('fitting:result:compare', args=['/1/1'])
    return url[:-4]

