from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.forms import formset_factory

from accounts.models import User
from core import visibility

from .models import EntityFile, ModelEntity, ProtocolEntity, ModelGroup, Story


# Helper dictionary for determining whether visibility of model groups / stories and their models works together
vis_ord = {'private': 0,
           'moderated': 1,
           'public': 2}


class EntityForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating an entirely new entity."""
    def clean_name(self):
        name = self.cleaned_data['name']
        if self._meta.model.objects.filter(name=name, author=self.user).exists():
            raise ValidationError(
                'You already have a %s named "%s"' % (self._meta.model.display_type, name))

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


class EntityRenameForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for renaming an existing entity."""

    def clean_name(self):
        name = self.cleaned_data['name']
        if self._meta.model.objects.filter(author=self.user, name=name).exists():
            raise ValidationError(
                'You already have a %s named "%s"' % (self._meta.model.display_type, name))

        return name


class ModelEntityRenameForm(EntityRenameForm):
    class Meta:
        model = ModelEntity
        fields = ['name']


class ProtocolEntityRenameForm(EntityRenameForm):
    class Meta:
        model = ProtocolEntity
        fields = ['name']


class ModelEntityForm(EntityForm):
    class Meta:
        model = ModelEntity
        fields = ['name']


class ProtocolEntityForm(EntityForm):
    class Meta:
        model = ProtocolEntity
        fields = ['name']


class EntityVersionForm(forms.Form):
    """Used to create a new version of an existing entity."""
    parent_hexsha = forms.CharField(required=False, widget=forms.HiddenInput)

    visibility = forms.ChoiceField(
        choices=visibility.CHOICES,
        help_text=visibility.HELP_TEXT.replace('\n', '<br />'),
    )
    tag = forms.CharField(
        help_text='Optional short label for this version',
        required=False,
        validators=[RegexValidator(r'^[-_A-Za-z0-9]+$', 'Please enter a valid tag name. '
                                                        'Only letters, numbers, dashes or underscores are allowed.')])
    commit_message = forms.CharField(
        label='Description of this version',
        widget=forms.Textarea)
    rerun_expts = forms.BooleanField(
        label='Re-run experiments involving the previous version of this %s',
        widget=forms.CheckboxInput(attrs={'class': 'inline'}),
        required=False)

    def __init__(self, *args, **kwargs):
        entity_type = kwargs.pop('entity_type')
        super().__init__(*args, **kwargs)
        rerun_field = self.fields.get('rerun_expts', None)
        if rerun_field:
            rerun_field.label = rerun_field.label % entity_type


class EntityChangeVisibilityForm(UserKwargModelFormMixin, forms.Form):
    visibility = forms.ChoiceField(
        choices=visibility.CHOICES,
        help_text=visibility.HELP_TEXT.replace('\n', '<br />'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = kwargs.pop('user')

        if not user.has_perm('entities.moderator'):
            self.fields['visibility'].choices.remove((
                visibility.Visibility.MODERATED, 'Moderated')
            )


class EntityTagVersionForm(forms.Form):
    tag = forms.CharField(
        label='New tag',
        help_text='Short label for this version',
        required=True,
        validators=[RegexValidator(r'^[-_A-Za-z0-9]+$', 'Please enter a valid tag name.'
                                                        ' Only letters, numbers, dashes or underscores are allowed.')])


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
        user = self._get_user(email)
        if not user:
            raise ValidationError('User not found')
        if user == self.entity.author:
            raise ValidationError("Cannot add because user is the author")
        self.cleaned_data['user'] = user
        return email

    def add_collaborator(self):
        if 'user' in self.cleaned_data:
            self.entity.add_collaborator(self.cleaned_data['user'])

    def remove_collaborator(self):
        if 'user' in self.cleaned_data:
            self.entity.remove_collaborator(self.cleaned_data['user'])


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


class ModelGroupForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating a new model group."""
    visibility = forms.ChoiceField(
        choices=visibility.CHOICES,
        help_text=visibility.HELP_TEXT.replace('\n', '<br />'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.current_title = None  # current title
        # Only show models I can can see
        self.fields['models'].queryset = ModelEntity.objects.visible_to_user(self.user)

        # Save current details if we have them
        instance = kwargs.get('instance', None)
        if instance:
            self.current_title = instance.title
            # only author can change visibility
            self.fields['visibility'].disabled = not instance.is_visibility_editable_by(self.user)

            # make sure currently selected models are not filtered out even if they are not visible to the current user
            current_models_ids = [model.id for model in instance.models.all()]
            self.fields['models'].queryset |= ModelEntity.objects.filter(id__in=current_models_ids)

        if not self.user.has_perm('entities.moderator'):
            self.fields['visibility'].choices.remove((
                visibility.Visibility.MODERATED, 'Moderated')
            )

    class Meta:
        model = ModelGroup
        fields = ['title', 'visibility', 'models']

    def clean_title(self):
        title = self.cleaned_data['title']
        if title != self.current_title and self._meta.model.objects.filter(title=title, author=self.user).exists():
            raise ValidationError(
                'You already have a model group named "%s"' % title)
        return title

    def clean_models(self):
        models = self.cleaned_data['models']
        visibility = self.cleaned_data['visibility']
        if any([vis_ord[m.visibility] < vis_ord[visibility] for m in models]):
            raise ValidationError(
                'The visibility of your selected models is too restrictive for the selected visibility of this model group')
        return models

    def save(self, **kwargs):
        modelgroup = super().save(commit=False)
        if not hasattr(modelgroup, 'author') or modelgroup.author is None:
            modelgroup.author = self.user
        modelgroup.save()
        self.save_m2m()
        return modelgroup


class StoryForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating a new story."""
    visibility = forms.ChoiceField(
        choices=visibility.CHOICES,
        help_text=visibility.HELP_TEXT.replace('\n', '<br />'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.current_title = None  # current title
        # Only show models and modelgroups I can can see
        self.fields['othermodels'].queryset = ModelEntity.objects.visible_to_user(self.user)
        visible_modelgroups = [m.pk for m in ModelGroup.objects.all() if m.visible_to_user(self.user)]
        self.fields['modelgroups'].queryset = ModelGroup.objects.filter(pk__in=visible_modelgroups)

        # Save current details if we have them
        instance = kwargs.get('instance', None)
        if instance:
            self.current_title = instance.title
            # only author can change visibility
            self.fields['visibility'].disabled = not instance.is_visibility_editable_by(self.user)

            # make sure currently selected models and model groups are not filtered out even if they are not visible to the current user
            current_othermodels_ids = [model.id for model in instance.othermodels.all()]
            current_modelgroups_ids = [model.id for model in instance.modelgroups.all()]
            self.fields['othermodels'].queryset |= ModelEntity.objects.filter(id__in=current_othermodels_ids)
            self.fields['modelgroups'].queryset |= ModelGroup.objects.filter(id__in=current_modelgroups_ids)

        if not self.user.has_perm('entities.moderator'):
            self.fields['visibility'].choices.remove((
                visibility.Visibility.MODERATED, 'Moderated')
            )

    class Meta:
        model = Story
        fields = ['title', 'visibility', 'modelgroups', 'othermodels', 'description']

    def clean_title(self):
        title = self.cleaned_data['title']
        if title != self.current_title and self._meta.model.objects.filter(title=title, author=self.user).exists():
            raise ValidationError(
                'You already have a model group named "%s"' % title)
        return title

    def clean_modelgroups(self):
        modelgroups = self.cleaned_data['modelgroups']
        visibility = self.cleaned_data['visibility']
        if any([vis_ord[m.visibility] < vis_ord[visibility] for m in modelgroups]):
            raise ValidationError(
                'The visibility of your selected model groups is too restrictive for the selected visibility of this story')
        return modelgroups


    def clean_othermodels(self):
        othermodels = self.cleaned_data['othermodels']
        visibility = self.cleaned_data['visibility']
        if any([vis_ord[m.visibility] < vis_ord[visibility] for m in othermodels]):
            raise ValidationError(
                'The visibility of your selected models is too restrictive for the selected visibility of this story')
        return othermodels

    def save(self, **kwargs):
        story = super().save(commit=False)
        if not hasattr(story, 'author') or story.author is None:
            story.author = self.user
        story.save()
        self.save_m2m()
        return story
