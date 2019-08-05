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
def can_create_dataset(context):
    user = context['user']
    return user.has_perm('datasets.create_dataset')


@register.filter
def url_dataset(dataset):
    if dataset.archive_path.exists():
        url_name = 'datasets:detail'
    else:
        url_name = 'datasets:addfiles'
    return reverse(url_name, args=[dataset.id])
