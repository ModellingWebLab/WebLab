from django import template
from django.core.urlresolvers import reverse


register = template.Library()


@register.simple_tag(takes_context=True)
def can_create_dataset(context):
    user = context['user']
    return user.has_perm('datasets.create_dataset_experiment')

@register.filter
def url_dataset(dataset):
    url_name = 'datasets:detail'
    return reverse(url_name, args=[dataset.id])


