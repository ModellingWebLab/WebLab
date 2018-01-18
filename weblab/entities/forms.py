from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError

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
        fields = ['name', 'visibility']


class ProtocolEntityForm(EntityForm):
    class Meta:
        model = ProtocolEntity
        fields = ['name', 'visibility']


class EntityVersionForm(forms.Form):
    tag = forms.CharField()
    commit_message = forms.CharField(widget=forms.Textarea)


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = EntityFile
        fields = ['upload']
