from entities.forms import EntityForm
from entities.models import ProtocolEntity

from .models import FittingSpec


class FittingSpecForm(EntityForm):
    """Used for creating an entirely new fitting specification."""
    class Meta:
        model = FittingSpec
        fields = ['name', 'protocol']

    def __init__(self, *args, **kwargs):
        """Only show visible protocols in the selection."""
        super().__init__(*args, **kwargs)
        self.fields['protocol'].queryset = ProtocolEntity.objects.visible_to_user(self.user)

    # TODO: Perhaps sort available protocols so 'mine' first, then moderated, then others?
