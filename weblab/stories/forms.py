import re
from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory, inlineformset_factory

from accounts.models import User
from core import visibility

from entities.forms import EntityCollaboratorForm, BaseEntityCollaboratorFormSet
from entities.models import ModelEntity, ModelGroup
from experiments.models import Experiment
from .models import Story, SimpleStory


# Helper dictionary for determining whether visibility of model groups / stories and their models works together
vis_ord = {'private': 0,
           'moderated': 1,
           'public': 2}


class StoryCollaboratorForm(EntityCollaboratorForm):
    def clean_email(self):
        email = super().clean_email()
        user = self._get_user(email)
        othermodels = self.entity.othermodels.all()
        modelgroups = self.entity.modelgroups.all()
        experiments = self.entity.experiments.all()
        visible_entities = ModelEntity.objects.visible_to_user(user)
        visible_model_groups = [m for m in ModelGroup.objects.all() if m.visible_to_user(user)]
        visible_experiments = [e for e in Experiment.objects.all() if e.is_visible_to_user(user)]
        if any (m not in visible_entities for m in othermodels):
            raise ValidationError("User %s does not have access to all models in the story" % (user.full_name))
        if any (m not in visible_model_groups for m in modelgroups):
            raise ValidationError("User %s does not have access to all model groups in the story" % (user.full_name))
        if any (e not in visible_experiments for e in experiments):
            raise ValidationError("User %s does not have access to all experiments in the story" % (user.full_name))
        return email


StoryCollaboratorFormSet = formset_factory(
    StoryCollaboratorForm,
    BaseEntityCollaboratorFormSet,
    can_delete=True,
)


class StoryForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating a new story."""

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

        choices = list(visibility.CHOICES)
        help_text = visibility.HELP_TEXT
        if not self.user.has_perm('entities.moderator') and not (instance and instance.visibility == visibility.Visibility.MODERATED):
            choices.remove((visibility.Visibility.MODERATED, 'Moderated'))
            help_text = re.sub('Moderated.*\n', '', help_text)

        self.fields['visibility'] = forms.ChoiceField(
            choices=choices,
            help_text=help_text.replace('\n', '<br />'),
            disabled = self.fields['visibility'].disabled
        )

    class Meta:
        model = Story
        fields = ['title', 'visibility', 'modelgroups', 'othermodels', 'description', 'experiments']

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

    def clean_experiments(self):
        experiments = self.cleaned_data['experiments']
        visibility = self.cleaned_data['visibility']
        if any([vis_ord[m.visibility] < vis_ord[visibility] for m in experiments]):
            raise ValidationError(
                'The visibility of your selected experiments is too restrictive for the selected visibility of this story')
        return experiments

    def save(self, **kwargs):
        story = super().save(commit=False)
        if not hasattr(story, 'author') or story.author is None:
            story.author = self.user
        story.save()
        self.save_m2m()
        return story



















class StoryPartForm(forms.Form):
    description = forms.CharField(widget=forms.Textarea)
#    email = forms.EmailField(
#        widget=forms.EmailInput(attrs={'placeholder': 'Email address of user'})
#    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
#        if self.initial.get('email'):
#            self.fields['email'].widget = forms.HiddenInput()
#            self.collaborator = self._get_user(self.initial['email'])
#
#    def _get_user(self, email):
#        try:
#            return User.objects.get(email=email)
#        except User.DoesNotExist:
#            return None
#
#    def clean_email(self):
#        email = self.cleaned_data['email']
#        user = self._get_user(email)
#        if not user:
#            raise ValidationError('User not found')
#        if user == self.entity.author:
#            raise ValidationError("Cannot add because user is the author")
#        self.cleaned_data['user'] = user
#        return email
#
#    def add_collaborator(self):
#        if 'user' in self.cleaned_data:
#            self.entity.add_collaborator(self.cleaned_data['user'])
#
#    def remove_collaborator(self):
#        if 'user' in self.cleaned_data:
#            self.entity.remove_collaborator(self.cleaned_data['user'])
#    def clean_description(self):
#        assert False, "descr "+ str(self.cleaned_data['description'])


class BaseStoryPartFormSet(forms.BaseFormSet):
    def save(self):
        assert False, str(self.forms)
#        for form in self.forms:
#            form.add_collaborator()
#
#        for form in self.deleted_forms:
#            form.remove_collaborator()


StoryPartFormSet = formset_factory(
    StoryPartForm,
    BaseStoryPartFormSet,
    can_delete=True,
#    extra=2,
    can_order=True,
)


class SimpleStoryForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating a new story."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
#        self.user = kwargs.pop('user',None)
        # Only show models and modelgroups I can can see
#        self.fields['othermodels'].queryset = ModelEntity.objects.visible_to_user(self.user)
#        visible_modelgroups = [m.pk for m in ModelGroup.objects.all() if m.visible_to_user(self.user)]
#        self.fields['modelgroups'].queryset = ModelGroup.objects.filter(pk__in=visible_modelgroups)

        choices = list(visibility.CHOICES)
        help_text = visibility.HELP_TEXT
        if not self.user.has_perm('entities.moderator') and not (instance and instance.visibility == visibility.Visibility.MODERATED):
            choices.remove((visibility.Visibility.MODERATED, 'Moderated'))
            help_text = re.sub('Moderated.*\n', '', help_text)

        self.fields['visibility'] = forms.ChoiceField(
            choices=choices,
            help_text=help_text.replace('\n', '<br />'),
            disabled = self.fields['visibility'].disabled
        )

    class Meta:
        model = SimpleStory
        fields = ['title', 'visibility']

    def clean_title(self):
        title = self.cleaned_data['title']
        if SimpleStory.objects.filter(title=title, author=self.user).exists():
            raise ValidationError(
                'You already have a story named "%s"' % title)
        return title

#    def save(self, **kwargs):
#        pass
#        assert False, str(kwargs)
#        simplestory = super().save(commit=False)
#        if not hasattr(simplestory, 'author') or simplestory.author is None:
#            simplestory.author = self.user
#        simplestory.save()
#        self.save_m2m()
#        return simplestory
