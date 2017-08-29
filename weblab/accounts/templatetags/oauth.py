from django import template


register = template.Library()


@register.filter
def backend_name(backend):
    if backend.provider == 'google-oauth2':
        return 'Google'
    elif backend.provider == 'github':
        return 'GitHub'
