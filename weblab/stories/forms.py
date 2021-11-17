import re
from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory, inlineformset_factory

from core import visibility

from entities.forms import EntityCollaboratorForm, BaseEntityCollaboratorFormSet
from entities.models import ModelEntity, ModelGroup
from experiments.models import Experiment
from .models import Story, StoryText, StoryGraph
from repocache.models import CachedProtocolVersion, CachedModelVersion
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
        user = self.cleaned_data['user']
        for graph in StoryGraph.objects.filter(story=self.entity):
            if not graph.cachedprotocolversion.protocol.is_version_visible_to_user(graph.cachedprotocolversion.sha,
                                                                                   user):
                raise ValidationError("User %s does not have access to version of %s protocol" %
                                      (user.full_name, graph.cachedprotocolversion.protocol.name))
            for model_version in graph.cachedmodelversions.all():
                if not model_version.model.is_version_visible_to_user(model_version.sha, user):
                    raise ValidationError("User %s does not have access to version of %s model" %
                                          (user.full_name, model_version.model.name))
        return email


StoryCollaboratorFormSet = formset_factory(
    StoryCollaboratorForm,
    BaseEntityCollaboratorFormSet,
    can_delete=True,
)


class BaseStoryFormSet(forms.BaseFormSet):
    def save(self, story=None, **kwargs):
        for form in self.deleted_forms:
            form.delete(**kwargs)
        return [form.save(story=story, **kwargs) for form in self.ordered_forms]

    @staticmethod
    def get_modelgroup_choices(user):
        return [('', '--------- model group')] +\
               [('modelgroup' + str(modelgroup.pk), modelgroup.title) for modelgroup in ModelGroup.objects.all()
                if modelgroup.visible_to_user(user)] +\
               [('', '--------- model')] +\
               [('model' + str(model.repocache.latest_version.pk), model.name)
                for model in ModelEntity.objects.visible_to_user(user)
                if model.repocache.versions.count()]

    @staticmethod
    def get_protocol_choices(user, model_versions=None):
        # Get protocols for which the latest result run succesful
        # that users can see for the model(s) we're looking at
        return set((e.protocol_version.pk, e.protocol.name) for e in Experiment.objects.all()
                   if e.latest_result == Runnable.STATUS_SUCCESS and
                   e.is_visible_to_user(user)
                   and (model_versions is None or e.model_version in model_versions))

    @staticmethod
    def get_graph_choices(user, protocol_version=None, model_versions=None):
        experimentversions = [e.latest_version for e in Experiment.objects.all()
                              if e.latest_result == Runnable.STATUS_SUCCESS and
                              e.is_visible_to_user(user)
                              and (protocol_version is None or e.protocol == protocol_version.protocol)
                              and (model_versions is None or e.model_version in model_versions)]

        graph_files = []
        for experimentver in experimentversions:
            # find outputs-contents.csv
            try:
                plots_data_file = experimentver.open_file('outputs-default-plots.csv').read().decode("utf-8")
                plots_data_stream = io.StringIO(plots_data_file)
                for row in csv.DictReader(plots_data_stream):
                    graph_files.append((row['Data file name'], row['Data file name']))
            except FileNotFoundError:
                pass  # This experiemnt version has no graphs
        return graph_files


class StoryTextForm(UserKwargModelFormMixin, forms.ModelForm):
    class Meta:
        model = StoryText
        fields = ['description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ORDER'] = forms.IntegerField(required=False)

    def save(self, story=None, **kwargs):
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


class StoryGraphForm(UserKwargModelFormMixin, forms.ModelForm):
    class Meta:
        model = StoryGraph
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ORDER'] = forms.IntegerField(required=False)
        self.fields['currentGraph'] = forms.CharField(required=False)
        self.fields['update'] = forms.ChoiceField(required=False, initial='pk' not in self.initial,
                                                  choices=[('True', 'True'), ('', '')], widget=forms.RadioSelect)
        self.fields['models_or_group'] = forms.ChoiceField(required=False,
                                                           choices=StoryGraphFormSet.get_modelgroup_choices(self.user))
        self.fields['protocol'] = forms.ChoiceField(required=False,
                                                    choices=StoryGraphFormSet.get_protocol_choices(self.user))
        self.fields['graphfiles'] = forms.ChoiceField(required=False,
                                                      choices=StoryGraphFormSet.get_graph_choices(self.user))

    def clean_models_or_group(self):
        if self.cleaned_data.get('update', False) and self.cleaned_data['models_or_group'] == "":
            raise ValidationError("This field is required.")
        if not self.cleaned_data['models_or_group'].startswith('model'):
            raise ValidationError("The model of group field value should start with model or modelgroup.")
        return self.cleaned_data['models_or_group']

    def clean_protocol(self):
        if self.cleaned_data.get('update', False) and self.cleaned_data['protocol'] == "":
            raise ValidationError("This field is required.")
        return self.cleaned_data['protocol']

    def clean_graphfiles(self):
        if self.cleaned_data.get('update', False) and self.cleaned_data['graphfiles'] == "":
            raise ValidationError("This field is required.")
        return self.cleaned_data['graphfiles']

    def save(self, story=None, **kwargs):
        if 'pk' in self.initial:
            storygraph = StoryGraph.objects.get(pk=self.initial['pk'])
        else:
            storygraph = super().save(commit=False)
        storygraph.order = self.cleaned_data['ORDER']

        if self.cleaned_data.get('update', False):
            storygraph.story = story
            storygraph.graphfilename = self.cleaned_data['graphfiles']

            mk = self.cleaned_data['models_or_group']
            pk = self.cleaned_data['protocol']
            modelgroup = None
            if mk.startswith('modelgroup'):
                mk = int(mk.replace('modelgroup', ''))
                modelgroup = ModelGroup.objects.get(pk=mk)
                model_versions = [m.repocache.latest_version for m in modelgroup.models.all()
                                  if m.repocache.versions.count()]
            else:
                assert mk.startswith('model'), "The model of group field value should start with model or modelgroup."
                mk = int(mk.replace('model', ''))
                model_versions = CachedModelVersion.objects.filter(pk=mk)
            storygraph.cachedprotocolversion = CachedProtocolVersion.objects.get(pk=pk)
            if not hasattr(storygraph, 'author') or storygraph.author is None:
                storygraph.author = self.user
            storygraph.modelgroup = modelgroup
            storygraph.set_cachedmodelversions(model_versions)
        storygraph.save()
        return storygraph

    def delete(self, **kwargs):
        if 'pk' in self.initial:
            storygraph = StoryGraph.objects.get(pk=self.initial['pk'])
            storygraph.delete()


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
        fields = ['title', 'visibility', 'graphvisualizer']

    def clean_title(self):
        title = self.cleaned_data['title']
        if (not self.instance or self.instance.title != self.cleaned_data['title']) and \
                Story.objects.filter(title=title, author=self.user).exists():
            raise ValidationError(
                'You already have a story named "%s"' % title)
        return title

    def save(self, **kwargs):
        self.instance = super().save(commit=False)
        self.instance.title = self.cleaned_data['title']
        if not hasattr(self.instance, 'author') or self.instance.author is None:
            self.instance.author = self.user
        self.instance.save()
        return self.instance

