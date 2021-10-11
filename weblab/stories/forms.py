import re
from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory, inlineformset_factory

from core import visibility

from entities.forms import EntityCollaboratorForm, BaseEntityCollaboratorFormSet
from entities.models import ModelEntity, ModelGroup, ProtocolEntity
from experiments.models import Experiment
from .models import Story, StoryText, StoryGraph
from experiments.models import Runnable
import csv
import io


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
        if any(m not in visible_entities for m in othermodels):
            raise ValidationError("User %s does not have access to all models in the story" % (user.full_name))
        if any(m not in visible_model_groups for m in modelgroups):
            raise ValidationError("User %s does not have access to all model groups in the story" % (user.full_name))
        if any(e not in visible_experiments for e in experiments):
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

    def save(self, story=None, **kwargs):
        storytext = super().save(commit=False)
        if 'pk' in self.initial:
            storytext = StoryText.objects.get(pk=self.initial['pk'])
        else:
           storytext = super().save(commit=False)

        storytext.order = self.cleaned_data['ORDER']
        storytext.description = self.cleaned_data['description']
        if not hasattr(storytext, 'author') or storytext.author is None:
            storytext.author = self.user
        storytext.story = story
        storytext.save()
        return storytext

    def delete(self, **kwargs):
        if 'pk' in self.initial:
            storytext = StoryText.objects.get(pk=self.initial['pk'])
            storytext.delete()

    def clean_description(self):
        description = self.cleaned_data['description']
        if description == "":
            raise ValidationError('This field is required.')
        return description


class BaseStoryFormSet(forms.BaseFormSet):
    def save(self, story=None, **kwargs):
        for form in self.deleted_forms:
            form.delete(**kwargs)
        return [form.save(story=story, **kwargs) for form in self.ordered_forms]

    @staticmethod
    def get_modelgroup_choices(user):
        return [('', '--------- model group')] +\
               [('modelgroup' + str(modelgroup.pk), modelgroup.title) for modelgroup in ModelGroup.objects.all()
                if modelgroup.visible_to_user(user) and any(model.repocache.versions.count() for model in modelgroup.models.all())] +\
               [('', '--------- model')] +\
               [('model' + str(model.pk), model.name) for model in ModelEntity.objects.visible_to_user(user) if model.repocache.versions.count()]

    @staticmethod
    def get_protocol_choices(user, models=None):
        # Get protocols for which the latest result run succesful
        # that users can see for the model(s) we're looking at
        return set((e.protocol.pk, e.protocol.name) for e in Experiment.objects.all()
                   if e.latest_result == Runnable.STATUS_SUCCESS and
                   e.is_visible_to_user(user)
                   and (models is None or e.model in models))

    @staticmethod
    def get_graph_choices(user, protocol=None, models=None):
        experimentversions = [e.latest_version for e in Experiment.objects.all()
                              if e.latest_result == Runnable.STATUS_SUCCESS and
                              e.is_visible_to_user(user)
                              and (protocol is None or e.protocol == protocol)
                              and (models is None or e.model in models)]

        files = set()
        for experimentver in experimentversions:
            # find outputs-contents.csv
            try:
                plots_data_file = experimentver.open_file('outputs-default-plots.csv').read().decode("utf-8")
                plots_data_stream = io.StringIO(plots_data_file)
                for row in csv.DictReader(plots_data_stream):
                    files.add(row['Data file name'])
            except FileNotFoundError:
                pass  # This experiemnt version has no graphs
        return [(f, f) for f in files]


StoryTextFormSet = inlineformset_factory(
    parent_model=Story,
    model=StoryText,
    form=StoryTextForm,
    formset=BaseStoryFormSet,
    fields=['description'],
    can_delete=True,
    can_order=True,
    extra=0,
    min_num=0,
)


class StoryGraphForm(UserKwargModelFormMixin, forms.ModelForm):
    class Meta:
        model = StoryGraph
        fields = ['graphfilename']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['models_or_group'] = forms.ChoiceField(label='Select protocol', required=True,
                                                           choices=StoryGraphFormSet.get_modelgroup_choices(self.user))
        self.fields['protocol'] = forms.ChoiceField(label='Select protocol', required=True,
                                                    choices=StoryGraphFormSet.get_protocol_choices(self.user))
        self.fields['graphfiles'] = forms.ChoiceField(label='Select graph', required=True,
                                                      choices=StoryGraphFormSet.get_graph_choices(self.user))

    def save(self, story=None, **kwargs):
        if 'pk' in self.initial:
            storygraph = StoryGraph.objects.get(pk=self.initial['pk'])
        else:
            storygraph = super().save(commit=False)
        storygraph.story = story
        storygraph.order = self.cleaned_data['ORDER']
        storygraph.graphfilename = self.cleaned_data['graphfiles']

        mk = self.cleaned_data['models_or_group']
        pk = self.cleaned_data['protocol']
        modelgroup = None
        if mk.startswith('modelgroup'):
            mk = int(mk.replace('modelgroup', ''))
            modelgroup = ModelGroup.objects.get(pk=mk)
            models = modelgroup.models.all()
        elif mk.startswith('model'):
            mk = int(mk.replace('model', ''))
            models = ModelEntity.objects.filter(pk=mk)
        storygraph.cachedprotocolversion = ProtocolEntity.objects.get(pk=pk).repocache.latest_version
        if not hasattr(storygraph, 'author') or storygraph.author is None:
            storygraph.author = self.user
        storygraph.modelgroup = modelgroup
        storygraph.save()
        storygraph.cachedmodelversions.clear()
        storygraph.cachedmodelversions.set([m.repocache.latest_version for m in models if m.repocache.versions.count()])
        return storygraph


    def delete(self, **kwargs):
        if 'pk' in self.initial:
            storygraph = StoryGraph.objects.get(pk=self.initial['pk'])
            storygraph.delete()


StoryGraphFormSet = inlineformset_factory(
    parent_model=Story,
    model=StoryGraph,
    form=StoryGraphForm,
    formset=BaseStoryFormSet,
    fields=[],
    can_delete=True,
    can_order=True,
    extra=0,
    min_num=0,
)


class StoryForm(UserKwargModelFormMixin, forms.ModelForm):
    """Used for creating a new story."""
    template_name = 'stories/story_form.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = kwargs.pop('user', None)

        # Save current details if we have them
        instance = kwargs.get('instance', None)

        choices = list(visibility.CHOICES)
        help_text = visibility.HELP_TEXT
        if not self.user.has_perm('entities.moderator') and not (instance and instance.visibility ==
                                                                 visibility.Visibility.MODERATED):
            choices.remove((visibility.Visibility.MODERATED, 'Moderated'))
            help_text = re.sub('Moderated.*\n', '', help_text)

        self.fields['visibility'] = forms.ChoiceField(
            choices=choices,
            help_text=help_text.replace('\n', '<br />'),
            disabled=self.fields['visibility'].disabled
        )

    class Meta:
        model = Story
        fields = ['title', 'visibility']

    def clean_title(self):
        title = self.cleaned_data['title']
        if not hasattr(self, 'story') and Story.objects.filter(title=title, author=self.user).exists():
            raise ValidationError(
                'You already have a story named "%s"' % title)
        return title

    def save(self, **kwargs):
        story = getattr(self, 'story', super().save(commit=False))
        story.title = self.cleaned_data['title']
        if not hasattr(story, 'author') or story.author is None:
            story.author = self.user
        story.save()
        return story
