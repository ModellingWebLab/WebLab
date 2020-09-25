from braces.forms import UserKwargModelFormMixin
from django.core.exceptions import ValidationError
from entities.forms import EntityForm, EntityVersionForm, EntityRenameForm
from entities.models import ProtocolEntity
from django import forms
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


class FittingSpecVersionForm(EntityVersionForm):
    """Used for creating a new version of a fitting specification.

    This works almost the same as other entities, except we can't re-run experiments.
    """
    rerun_expts = None


class FittingSpecRenameForm(EntityRenameForm):
    """Used for renaming an existing entity."""
    class Meta:
        model = FittingSpec
        fields = ['name']
