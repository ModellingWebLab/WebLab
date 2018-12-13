from braces.forms import UserKwargModelFormMixin
from django import forms
from django.forms import formset_factory
from django.core.exceptions import ValidationError
from guardian.shortcuts import assign_perm, remove_perm

from accounts.models import User
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
    visibility = forms.ChoiceField(
        choices=visibility.CHOICES,
        help_text=visibility.HELP_TEXT.replace('\n', '<br />'),
    )
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


class EntityCollaboratorForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Email address of user'})
    )

    def __init__(self, *args, **kwargs):
        self.entity = kwargs.pop('entity')
        super().__init__(*args, **kwargs)
        if self.initial.get('email'):
            self.fields['email'].widget = forms.HiddenInput()
            self.collaborator = self._get_user(self.initial['email'])

    def _get_user(self, email):
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None

    def clean_email(self):
        email = self.cleaned_data['email']
        if email:
            user = self._get_user(email)
            if not user:
                raise ValidationError('User not found')
            self.cleaned_data['user'] = user
        return email

    def add_collaborator(self):
        if 'user' in self.cleaned_data:
            assign_perm('edit_entity', self.cleaned_data['user'], self.entity)

    def remove_collaborator(self):
        if 'user' in self.cleaned_data:
            remove_perm('edit_entity', self.cleaned_data['user'], self.entity)


class BaseEntityCollaboratorFormSet(forms.BaseFormSet):
    def save(self):
        for form in self.forms:
            form.add_collaborator()

        for form in self.deleted_forms:
            form.remove_collaborator()


EntityCollaboratorFormSet = formset_factory(
    EntityCollaboratorForm,
    BaseEntityCollaboratorFormSet,
    can_delete=True,
)


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = EntityFile
        fields = ['upload']
