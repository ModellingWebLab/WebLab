USER_FIELDS = ['email']


def create_user(strategy, details, backend, user=None, *args, **kwargs):
    """
    Adapted version of core create_user - we need to take additional fields
    from various different social backends.
    """
    if user:
        return {'is_new': False}

    fields = dict((name, kwargs.get(name, details.get(name)))
                  for name in backend.setting('USER_FIELDS', USER_FIELDS))
    if not fields:
        return

    # Google oauth sends full name in this field
    if 'fullname' in details:
        fields['full_name'] = details['fullname']

    return {
        'is_new': True,
        'user': strategy.create_user(**fields)
    }
