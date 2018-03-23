PRIVATE = 'private'
RESTRICTED = 'restricted'
PUBLIC = 'public'

CHOICES = (
    (PRIVATE, 'Private'),
    (RESTRICTED, 'Restricted'),
    (PUBLIC, 'Public')
)

HELP_TEXT = (
    'Public = anyone can view\n'
    'Restricted = logged in users can view\n'
    'Private = only you can view'
)


def get_joint_visibility(*visibilities):
    """
    :return joint visibility of a set of visibilities
    """
    # Ordered by most conservative first
    levels = [
        PRIVATE, RESTRICTED, PUBLIC,
    ]

    # Use the most conservative of the two entities' visibilities
    return min(
        levels.index(vis)
        for vis in visibilities
    )
