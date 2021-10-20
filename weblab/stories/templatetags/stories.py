from django import template
from django.urls import reverse


register = template.Library()


@register.simple_tag(takes_context=True)
def can_delete_story(context, story):
    user = context['user']
    return story.is_deletable_by(user)


@register.simple_tag(takes_context=True)
def can_manage_story(context, story):
    user = context['user']
    return story.is_managed_by(user)

@register.simple_tag(takes_context=True)
def url_experiment_comparison_json(context, experiment_versions):
    """
    Build URL for experiment comparison json
    """
    return reverse('experiments:compare_json', args=[experiment_versions])
