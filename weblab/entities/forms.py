from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError

from core import visibility

from .models import EntityFile, ModelEntity, ProtocolEntity


class EntityForm(UserKwargModelFormMixin, forms.ModelForm):
    def clean_name(self):
        name = self.cleaned_data['name']
        if self._meta.model.objects.filter(name=name).exists():
            raise ValidationError(
                'You already have a %s named "%s"' % (self.entity_type, name))

        return name

    def save(self, **kwargs):
        entity = super().save(commit=False)
        entity.author = self.user
        entity.entity_type = self.entity_type
        entity.save()
        self.save_m2m()
        return entity

    @property
    def entity_type(self):
        return self._meta.model.entity_type


class ModelEntityForm(EntityForm):
    class Meta:
        model = ModelEntity
        fields = ['name']


class ProtocolEntityForm(EntityForm):
    class Meta:
        model = ProtocolEntity
        fields = ['name']


class EntityVersionForm(forms.Form):
    tag = forms.CharField(
        help_text='Optional short label for this version',
        required=False)
    commit_message = forms.CharField(
        label='Description of this version',
        widget=forms.Textarea)


class EntityChangeVisibilityForm(forms.Form):
    visibility = forms.ChoiceField(
        choices=visibility.CHOICES,
        help_text=visibility.HELP_TEXT.replace('\n', '<br />'),
    )


class EntityTagVersionForm(forms.Form):
    tag = forms.CharField(
        label='New tag',
        help_text='Short label for this version',
        required=True)


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = EntityFile
        fields = ['upload']
