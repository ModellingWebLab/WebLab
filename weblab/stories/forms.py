import re
from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory, inlineformset_factory, modelformset_factory

from accounts.models import User
from core import visibility

from entities.forms import EntityCollaboratorForm, BaseEntityCollaboratorFormSet
from entities.models import ModelEntity, ModelGroup
from experiments.models import Experiment
from .models import Story, SimpleStory, StoryPart


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



















class StoryPartForm(UserKwargModelFormMixin, forms.ModelForm):

    class Meta:
        model = StoryPart
        fields = ['description']

    def save(self, simplestory=None, order=0, **kwargs):
        storypart = super().save(commit=False)
        storypart.order = order
        if not hasattr(storypart, 'author') or storypart.author is None:
            storypart.author = self.user
        storypart.story=simplestory
        storypart.save()
        return storypart

    @property
    def order(self):
        return float('inf') if self.cleaned_data['DELETE'] else self.cleaned_data['ORDER']

class BaseStoryPartFormSet(forms.BaseFormSet):
    def save(self, simplestory=None, **kwargs):
        # delete deleted parts if there are any

        return [form.save(simplestory=simplestory, order=order, **kwargs) 
                for order, form in enumerate(sorted(self.ordered_forms, key=lambda f: f.order))]


StoryPartFormSet = inlineformset_factory(
    parent_model=SimpleStory,
    model=StoryPart,
    form=StoryPartForm,
    formset=BaseStoryPartFormSet,
    fields=['description'],
    can_delete=True,
    can_order=True,
    extra=0,
    min_num=1,
)


class SimpleStoryForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating a new story."""

    template_name = 'stories/simplestory_form.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = kwargs.pop('user', None)
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

    def save(self, **kwargs):
        simplestory = super().save(commit=False)
        if not hasattr(simplestory, 'author') or simplestory.author is None:
            simplestory.author = self.user
        simplestory.save()
        return simplestory
