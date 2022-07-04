from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def can_delete_story(context, story):
    user = context['user']
    return story.is_deletable_by(user)


@register.simple_tag(takes_context=True)
def can_manage_story(context, story):
    user = context['user']
    return story.is_managed_by(user)
