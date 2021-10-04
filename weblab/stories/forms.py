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
from .models import Story, StoryText, StoryGraph
from experiments.models import ExperimentVersion
from entities.models import ModelEntity, ModelGroup, ProtocolEntity
import csv, io


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


class StoryTextForm(UserKwargModelFormMixin, forms.ModelForm):
    class Meta:
        model = StoryText
        fields = ['description']

    def save(self, story=None, order=0, **kwargs):
        storytext = super().save(commit=False)
        storytext.order = order
        if not hasattr(storytext, 'author') or storytext.author is None:
            storytext.author = self.user
        storytext.story=story
        storytext.save()
        return storytext

    @property
    def order(self):
        return float('inf') if self.cleaned_data['DELETE'] else self.cleaned_data['ORDER']

class BaseStoryTextFormSet(forms.BaseFormSet):
    def save(self, story=None, **kwargs):
         return [form.save(story=story, order=form.cleaned_data['order'], **kwargs) for form in self.ordered_forms]


StoryTextFormSet = inlineformset_factory(
    parent_model=Story,
    model=StoryText,
    form=StoryTextForm,
    formset=BaseStoryTextFormSet,
    fields=['description'],
    can_delete=True,
    can_order=True,
    extra=0,
    min_num=1,
)


class StoryGraphForm(UserKwargModelFormMixin, forms.ModelForm):
    class Meta:
        model = StoryGraph
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['models_or_group']  = forms.ModelChoiceField(label='Select model or model group', required = True,
                                                                 queryset=ModelEntity.objects.visible_to_user(self.user))
        self.fields['protocol']  = forms.ModelChoiceField(label='Select protocol', required = True,
                                                                 queryset=ProtocolEntity.objects.visible_to_user(self.user))
        # get all possible graphs
        experimentversions = ExperimentVersion.objects.all()
        files = set()
        for experimentver in experimentversions:
            # find outputs-contents.csv
            try:
                plots_data_file = experimentver.open_file('outputs-default-plots.csv').read().decode("utf-8")
                plots_data_stream = io.StringIO(plots_data_file)
                for row in csv.DictReader(plots_data_stream):
                    files.add((row['Data file name'], row['Data file name']))
            except FileNotFoundError:
                pass  # This experiment version has no graphs
        self.fields['graphfiles']  = forms.ChoiceField(label='Select graph', required = True,
                                                       choices=files)


StoryGraphFormSet = inlineformset_factory(
    parent_model=Story,
    model=StoryGraph,
    form=StoryGraphForm,
    formset=BaseStoryTextFormSet,
    fields=[],
    can_delete=True,
    can_order=True,
    extra=0,
    min_num=1,
)


class StoryForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating a new story."""

    template_name = 'stories/story_form.html'

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
        model = Story
        fields = ['title', 'visibility']

    def clean_title(self):
        title = self.cleaned_data['title']
        if Story.objects.filter(title=title, author=self.user).exists():
            raise ValidationError(
                'You already have a story named "%s"' % title)
        return title

    def save(self, **kwargs):
        story = super().save(commit=False)
        if not hasattr(story, 'author') or story.author is None:
            story.author = self.user
        story.save()
        return story
