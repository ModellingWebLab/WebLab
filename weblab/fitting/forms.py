from entities.forms import EntityForm

from .models import FittingSpec


class FittingSpecForm(EntityForm):
    """Used for creating an entirely new fitting specification."""
    class Meta:
        model = FittingSpec
        fields = ['name']

    # TODO: Add protocol link, like for datasets (ensuring visibility respected)
    # Perhaps sort available protocols so 'mine' first, then moderated, then others?
