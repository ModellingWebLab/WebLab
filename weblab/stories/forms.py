import re
from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory

from accounts.models import User
from core import visibility

from entities.forms import EntityCollaboratorForm, BaseEntityCollaboratorFormSet
from entities.models import ModelEntity, ModelGroup
from .models import Story


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
        visible_entities = ModelEntity.objects.visible_to_user(user)
        visible_model_groups = [m for m in ModelGroup.objects.all() if m.visible_to_user(user)]
        if any (m not in visible_entities for m in othermodels):
            raise ValidationError("User %s does not have access to all models in the story" % (user.full_name))
        if any (m not in visible_model_groups for m in modelgroups):
            raise ValidationError("User %s does not have access to all model groups in the story" % (user.full_name))
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

