from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError

from .models import Dataset, DatasetFile


class DatasetForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating an entirely new Dataset."""
    class Meta:
        model = Dataset
        fields = ['name', 'visibility', 'protocol', 'description']

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
