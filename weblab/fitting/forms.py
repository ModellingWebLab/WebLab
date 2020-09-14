from django import forms
from django.core.exceptions import ValidationError

from entities.forms import EntityForm, EntityVersionForm
from entities.models import ProtocolEntity

from .models import FittingResult, FittingSpec


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


class FittingResultCreateForm(forms.ModelForm):
    class Meta:
        model = FittingResult
        fields = ('model', 'model_version', 'protocol', 'protocol_version',
                  'fittingspec', 'fittingspec_version', 'dataset')

    def clean(self):
        if self.cleaned_data['model_version'].model != self.cleaned_data['model']:
            raise ValidationError({'model_version': 'Model version must belong to model'})

        if self.cleaned_data['protocol_version'].protocol != self.cleaned_data['protocol']:
            raise ValidationError({'protocol_version': 'Protocol version must belong to protocol'})

        if self.cleaned_data['fittingspec_version'].fittingspec != self.cleaned_data['fittingspec']:
            raise ValidationError({'fittingspec_version': 'Fitting spec version must belong to fitting spec'})

        if self.cleaned_data['dataset'].protocol != self.cleaned_data['protocol']:
            raise ValidationError({'protocol': 'Protocol and dataset must match'})

        if self.cleaned_data['fittingspec'].protocol != self.cleaned_data['protocol']:
            raise ValidationError({'protocol': 'Protocol and fitting spec must match'})
