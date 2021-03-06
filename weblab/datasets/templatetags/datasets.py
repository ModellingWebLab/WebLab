from django import template
from django.urls import reverse


register = template.Library()


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


@register.simple_tag(takes_context=True)
def can_delete_entity(context, entity):
    user = context['user']
    return entity.is_deletable_by(user)


@register.simple_tag(takes_context=True)
def can_modify_dataset(context, dataset):
    user = context['user']
    return dataset.is_editable_by(user)


@register.simple_tag(takes_context=True)
def can_manage_dataset(context, dataset):
    user = context['user']
    return dataset.is_managed_by(user)
