from django import template
from django.core.urlresolvers import reverse


register = template.Library()


@register.simple_tag(takes_context=True)
def can_create_dataset(context):
    user = context['user']
    return user.has_perm('datasets.create_dataset_experiment')
