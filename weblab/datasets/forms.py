from braces.forms import UserKwargModelFormMixin
from django import forms
from django.forms import formset_factory
from django.core.exceptions import ValidationError

from accounts.models import User
from core import visibility

from .models import ExperimentalDataset, DatasetFile


class ExperimentalDatasetForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating an entirely new ExperimentalDataset."""
    def clean_name(self):
        name = self.cleaned_data['name']
        if self._meta.model.objects.filter(name=name).exists():
            raise ValidationError(
                'You already have a dataset named "%s"' % (name))

        return name

    def save(self, **kwargs):
        entity = super().save(commit=False)
        entity.author = self.user
        entity.entity_type = self.entity_type
        entity.save()
        self.save_m2m()
        return entity


# EntityCollaboratorFormSet = formset_factory(
#     EntityCollaboratorForm,
#     BaseEntityCollaboratorFormSet,
#     can_delete=True,
# )


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = DatasetFile
        fields = ['upload']
