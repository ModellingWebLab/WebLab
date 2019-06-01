from braces.forms import UserKwargModelFormMixin
from django import forms
from django.forms import formset_factory
from django.core.exceptions import ValidationError

from accounts.models import User
from core import visibility

from .models import ExperimentalDataset, DatasetFile


class ExperimentalDatasetForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating an entirely new ExperimentalDataset."""
    class Meta:
        model = ExperimentalDataset
        fields = ['name', 'visibility', 'protocol']

    def clean_name(self):
        name = self.cleaned_data['name']
        if self._meta.model.objects.filter(name=name).exists():
            raise ValidationError(
                'You already have a dataset named "%s"' % (name))
        return name

    def save(self, **kwargs):
        dataset = super().save(commit=False)
        dataset.author = self.user
        dataset.save()
        self.save_m2m()
        return dataset


class ExperimentalDatasetAddFilesForm(forms.Form):
    """Used to add files to a new dataset."""
    class Meta:
        model = ExperimentalDataset
        fields = ['description']

    description = forms.CharField(
        label='Description of this dataset',
        widget=forms.Textarea)

# EntityCollaboratorFormSet = formset_factory(
#     EntityCollaboratorForm,
#     BaseEntityCollaboratorFormSet,
#     can_delete=True,
# )


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = DatasetFile
        fields = ['upload']
