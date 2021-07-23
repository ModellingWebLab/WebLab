from braces.forms import UserKwargModelFormMixin
from datasets.models import Dataset
from django import forms
from django.core.exceptions import ValidationError
from entities.forms import EntityForm, EntityRenameForm, EntityVersionForm
from entities.models import ModelEntity, ProtocolEntity
from repocache.models import CachedFittingSpecVersion, CachedModelVersion, CachedProtocolVersion

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


class FittingSpecRenameForm(EntityRenameForm):
    """Used for renaming an existing entity."""
    class Meta:
        model = FittingSpec
        fields = ['name']


class VersionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.nice_version()


class FittingResultCreateForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating and running a new fitting result"""
    model_version = VersionChoiceField(queryset=CachedModelVersion.objects.all())
    protocol_version = VersionChoiceField(queryset=CachedProtocolVersion.objects.all())
    fittingspec_version = VersionChoiceField(queryset=CachedFittingSpecVersion.objects.all(),
                                             label='Fitting specification version')

    class Meta:
        model = FittingResult
        fields = ('model', 'model_version', 'protocol', 'protocol_version',
                  'fittingspec', 'fittingspec_version', 'dataset')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fittingspec'].label = 'Fitting specification'

        # Disable fields with preselected values
        # But only when there is no data bound - otherwise we will lose the
        # posted values of these fields from the submitted form.
        if not self.is_bound:
            self.fields['model'].disabled = bool(self.initial.get('model'))
            self.fields['protocol'].disabled = bool(self.initial.get('protocol'))
            self.fields['fittingspec'].disabled = bool(self.initial.get('fittingspec'))
            self.fields['dataset'].disabled = bool(self.initial.get('dataset'))

        # Ensure only visible entities and versions are available to user
        self.fields['model'].queryset = ModelEntity.objects.visible_to_user(self.user)
        self.fields['protocol'].queryset = ProtocolEntity.objects.visible_to_user(self.user)
        self.fields['fittingspec'].queryset = FittingSpec.objects.visible_to_user(self.user)
        self.fields['dataset'].queryset = Dataset.objects.visible_to_user(self.user)

        self.fields['model_version'].queryset = CachedModelVersion.objects.visible_to_user(self.user)
        self.fields['protocol_version'].queryset = CachedProtocolVersion.objects.visible_to_user(self.user)
        self.fields['fittingspec_version'].queryset = CachedFittingSpecVersion.objects.visible_to_user(self.user)

    def clean(self):
        # Check ownership of versions by entities
        model_version = self.cleaned_data.get('model_version')
        if model_version and model_version.model != self.cleaned_data.get('model'):
            raise ValidationError({'model_version': 'Model version must belong to model'})

        protocol_version = self.cleaned_data.get('protocol_version')
        if protocol_version and protocol_version.protocol != self.cleaned_data['protocol']:
            raise ValidationError({'protocol_version': 'Protocol version must belong to protocol'})

        fittingspec_version = self.cleaned_data.get('fittingspec_version')
        if fittingspec_version and fittingspec_version.fittingspec != self.cleaned_data['fittingspec']:
            raise ValidationError({'fittingspec_version': 'Fitting spec version must belong to fitting spec'})

        # Check linkage between protocols, datasets and fitting specs
        protocol = self.cleaned_data.get('protocol')
        dataset = self.cleaned_data.get('dataset')
        if dataset and dataset.protocol != protocol:
            raise ValidationError({'protocol': 'Protocol and dataset must match'})

        fittingspec = self.cleaned_data.get('fittingspec')
        if fittingspec and fittingspec.protocol != protocol:
            raise ValidationError({'protocol': 'Protocol and fitting spec must match'})
