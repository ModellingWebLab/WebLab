from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils.functional import cached_property

from entities.models import ProtocolEntity
from repocache.models import CachedProtocolVersion, ProtocolIoputs

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


# EntityCollaboratorFormSet = formset_factory(
#     EntityCollaboratorForm,
#     BaseEntityCollaboratorFormSet,
#     can_delete=True,
# )


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


class EntityVersionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.nice_version()


class BaseDatasetColumnMappingFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)

    @cached_property
    def proto_versions(self):
        return self.instance.protocol.cachedentity.versions.visible_to_user(self.user)

    @cached_property
    def proto_ioputs(self):
        return ProtocolIoputs.objects.filter(
            protocol_version__in=self.proto_versions,
            kind__in=(ProtocolIoputs.INPUT, ProtocolIoputs.OUTPUT)
        )

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['dataset'] = self.instance

        kwargs['protocol_versions'] = self.proto_versions
        kwargs['protocol_ioputs'] = self.proto_ioputs

        return kwargs


class DatasetColumnMappingForm(forms.ModelForm):
    protocol_version = EntityVersionChoiceField(
        queryset=CachedProtocolVersion.objects.none())

    def __init__(self, *args, **kwargs):
        protocol_versions = kwargs.pop('protocol_versions')
        protocol_ioputs = kwargs.pop('protocol_ioputs')
        self.dataset = kwargs.pop('dataset')
        super().__init__(*args, **kwargs)
        self.fields['protocol_version'].queryset = protocol_versions
        self.fields['protocol_version'].empty_label = None
        self.fields['protocol_ioput'].queryset = protocol_ioputs

    class Meta:
        model = DatasetColumnMapping
        fields = ['column_name', 'column_units', 'protocol_version', 'protocol_ioput']
        readonly_fields = ['column_name']


DatasetColumnMappingFormSet = inlineformset_factory(
    Dataset,
    DatasetColumnMapping,
    formset=BaseDatasetColumnMappingFormSet,
    form=DatasetColumnMappingForm,
)
