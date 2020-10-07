from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError

from entities.models import ProtocolEntity

from .models import Dataset, DatasetFile
from accounts.models import User


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


class DatasetTransferForm(UserKwargModelFormMixin, forms.Form):
    """Used for transferring an existing entity."""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Email address of user'})
    )

    def _get_user(self, email):
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None

    def clean_email(self):
        email = self.cleaned_data['email']
        user = self._get_user(email)
        if not user:
            raise ValidationError('User not found')

        self.cleaned_data['user'] = user
        return email


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

