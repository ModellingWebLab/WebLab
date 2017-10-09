import os.path

from braces.forms import UserKwargModelFormMixin
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from git import Repo

from .models import EntityUpload, ModelEntity, ProtocolEntity


class EntityForm(UserKwargModelFormMixin, forms.ModelForm):
    def clean_name(self):
        name = self.cleaned_data['name']
        if self._meta.model.objects.filter(name=name).exists():
            raise ValidationError('You already have a %s named "%s"' % (self.ENTITY_TYPE_NAME, name))
        if os.path.exists(str(settings.REPO_BASE / self._meta.model.get_repo_path(self.user.id, name))):
            raise ValidationError('You already have a %s repository named "%s"' % (self.ENTITY_TYPE_NAME, name))
        return name

    def save(self, **kwargs):
        entity = super().save(commit=False)
        entity.author = self.user
        entity.repository_url = entity.get_repo_path(entity.author.id, entity.name)

        Repo.init(str(settings.REPO_BASE / entity.repository_url))

        entity.save()
        self.save_m2m()
        return entity


class ModelEntityForm(EntityForm):
    ENTITY_TYPE_NAME = 'model'

    class Meta:
        model = ModelEntity
        fields = ['name', 'visibility']


class ProtocolEntityForm(EntityForm):
    ENTITY_TYPE_NAME = 'protocol'

    class Meta:
        model = ProtocolEntity
        fields = ['name', 'visibility']


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = EntityUpload
        fields = ['upload']
