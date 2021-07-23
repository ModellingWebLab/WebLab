from pint import UnitRegistry
from pint.errors import DefinitionSyntaxError, UndefinedUnitError

from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError
from entities.models import ProtocolEntity

from .models import Dataset, DatasetColumnMapping, DatasetFile


class DatasetForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating an entirely new Dataset."""
    class Meta:
        model = Dataset
        fields = ['name', 'visibility', 'protocol', 'description']

    def __init__(self, *args, **kwargs):
        """Only show visible protocols in the selection."""
        super().__init__(*args, **kwargs)
        self.fields['protocol'].queryset = ProtocolEntity.objects.visible_to_user(self.user)

    def clean_name(self):
        name = self.cleaned_data['name']
        if self._meta.model.objects.filter(name=name, author=self.user).exists():
            raise ValidationError(
                'You already have a dataset named "%s"' % (name))
        return name

    def save(self, **kwargs):
        dataset = super().save(commit=False)
        dataset.author = self.user
        dataset.save()
        self.save_m2m()
        return dataset


class DatasetAddFilesForm(forms.Form):
    """Used to add files to a new dataset."""
    class Meta:
        model = Dataset


class DatasetFileUploadForm(forms.ModelForm):
    class Meta:
        model = DatasetFile
        fields = ['upload']


class DatasetRenameForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for renaming an existing entity."""
    class Meta:
        model = Dataset
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data['name']
        if self._meta.model.objects.filter(author=self.user, name=name).exists():
            raise ValidationError(
                'You already have a dataset named "%s"' % name)

        return name


class DatasetColumnMappingForm(forms.ModelForm):
    """For setting up mappings between protocol ioputs
    and dataset columns"""
    class Meta:
        model = DatasetColumnMapping
        fields = ['dataset', 'protocol_version',
                  'column_name', 'column_units', 'protocol_ioput']
        widgets = {
            'dataset': forms.HiddenInput,
            'protocol_version': forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        self.dataset = kwargs.pop('dataset')
        protocol_ioputs = kwargs.pop('protocol_ioputs')
        super().__init__(*args, **kwargs)
        self.fields['protocol_ioput'].queryset = protocol_ioputs
        self.fields['column_name'].widget.attrs['readonly'] = 'readonly'

    def clean_protocol_version(self):
        proto_version = self.cleaned_data['protocol_version']
        if proto_version.protocol != self.dataset.protocol:
            raise ValidationError('Protocol version must belong to dataset protocol')
        return proto_version

    def clean_column_name(self):
        col_name = self.cleaned_data['column_name']
        if col_name not in self.dataset.column_names:
            raise ValidationError('Column name is not valid for this dataset')
        return col_name

    def clean_column_units(self):
        col_unit = self.cleaned_data['column_units']
        ureg = UnitRegistry()
        try:
            ureg(col_unit)
            return col_unit
        except (UndefinedUnitError, DefinitionSyntaxError):
            raise ValidationError('Must be a valid pint definition string')
