import re

from braces.forms import UserKwargModelFormMixin
from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory, inlineformset_factory

from core import visibility
from entities.forms import BaseEntityCollaboratorFormSet, EntityCollaboratorForm
from entities.models import ModelEntity, ModelGroup, ProtocolEntity

from .graph_filters import get_graph_file_names, get_modelgroups #, get_protocols
from .models import Story, StoryGraph, StoryText


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


class StoryTextForm(UserKwargModelFormMixin, forms.ModelForm):
    class Meta:
        model = StoryText
        fields = ['description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['number'] = forms.IntegerField(required=False)
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
        self.user = kwargs.pop('user', None)
        visible_model_choices = get_modelgroups(self.user)

        self.fields['number'] = forms.IntegerField(required=False)
        self.fields['ORDER'] = forms.IntegerField(required=False)
        self.fields['graphfilename'] = forms.CharField(required=False, widget=forms.HiddenInput)
        self.fields['currentGraph'] = forms.CharField(required=False)
        self.fields['experimentVersions'] = \
            forms.CharField(required=False, widget=forms.HiddenInput(attrs={'class': 'preview-graph-control'}))

        self.fields['experimentVersionsUpdate'] = \
            forms.CharField(required=False, widget=forms.HiddenInput(attrs={'class': 'preview-graph-control'}))

        self.fields['update'] = forms.ChoiceField(required=False, initial='pk' not in self.initial,
                                                  choices=[('True', 'True'), ('', '')], widget=forms.RadioSelect)
        self.fields['models_or_group'] = forms.CharField(required=False,
                                                         widget=forms.Select(attrs={'class': 'modelgroupselect'}, choices = visible_model_choices))
        self.fields['id_models'] = forms.CharField(required=False, widget=forms.SelectMultiple(attrs={'class': 'modelgroupselect'}, choices = visible_model_choices))

        self.fields['protocol'] = forms.CharField(required=False, widget=forms.Select(attrs={'class': 'graphprotocol'}))
        self.fields['graphfiles'] = forms.CharField(required=False, widget=forms.Select(attrs={'class': 'graphfiles'}))

        if 'initial' in kwargs:
            disabled = not kwargs['initial'].get('update', True)
            protocol = kwargs['initial'].get('protocol', '')

            self.fields['protocol'].widget.attrs['disabled'] = 'disabled' if disabled else False
            self.fields['graphfiles'].widget.attrs['disabled'] = 'disabled' if disabled else False

#    def clean(self):
#        cleaned_data = super().clean()
#        disabled = not cleaned_data['update']
#        self.fields['models_or_group'].widget.attrs['disabled'] = 'disabled' if disabled else False
#        self.fields['id_modelsp'].widget.attrs['disabled'] = 'disabled' if disabled else False
#        self.fields['protocol'].widget.attrs['disabled'] = 'disabled' if disabled else False
#        self.fields['graphfiles'].widget.attrs['disabled'] = 'disabled' if disabled else False
#        if not disabled:
##            self.fields['protocol'].widget.choices = \
##                [('', '--------- protocol')] + list(get_protocols(cleaned_data.get('models_or_group', ''),
##                                                                  self.user))
#            graph_coices = list(
#                get_graph_file_names(self.user,
#                                     cleaned_data.get('models_or_group', ''),
#                                     cleaned_data.get('protocol', ''))
#            )
#            if not graph_coices:
#                graph_coices = [('', '--------- graph')]
#            self.fields['graphfiles'].widget.choices = graph_coices
#        return cleaned_data
#
#    def clean_models_or_group(self):
#        if self.cleaned_data.get('update', False):
#            if self.cleaned_data.get('update', False) and self.cleaned_data['models_or_group'] == "":
#                raise ValidationError("This field is required.")
#            if not self.cleaned_data['models_or_group'].startswith('model'):
#                raise ValidationError("The model of group field value should start with model or modelgroup.")
#        return self.cleaned_data['models_or_group']
#
    def clean_id_models(self):
        self.fields['models_or_group'].disabled = not self.cleaned_data['update']
        self.fields['id_models'].disabled = not self.cleaned_data['update']
        if self.cleaned_data.get('update', False) and not self.cleaned_data['id_models']:
            raise ValidationError("This field is required.")
        return re.sub('\[|\]|\'| ', '', self.cleaned_data['id_models']).split(',')

    def clean_protocol(self):
        self.fields['protocol'].disabled = not self.cleaned_data['update']
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
            if not hasattr(storygraph, 'author') or storygraph.author is None:
                storygraph.author = self.user
            storygraph.story = story
            storygraph.graphfilename = self.cleaned_data['graphfiles']

            pk = self.cleaned_data['protocol']
            storygraph.cachedprotocolversion = ProtocolEntity.objects.get(pk=pk).repocache.latest_version

            modelgroups = set()
            model_versions = set()
            for model_or_group in self.cleaned_data['id_models']:
                if model_or_group.startswith('modelgroup'):
                    mk = int(model_or_group.replace('modelgroup', ''))
                    modelgroup = ModelGroup.objects.get(pk=mk)
                    model_versions |= set(m.repocache.latest_version for m in modelgroup.models.all()
                                      if m.repocache.versions.count())
                    modelgroups.add(modelgroup)
                else:
                    mk = int(model_or_group.replace('model', ''))
                    model_versions.add(ModelEntity.objects.get(pk=mk).repocache.latest_version) #.pk)

            storygraph.save()
            storygraph.modelgroups.set(modelgroups)
            storygraph.cachedmodelversions.set(model_versions)
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

    def clean(self):
        data = super().clean()
        if not getattr(self, 'num_parts', 0):
            raise ValidationError("Story is empty add at least one text box or graph. ")
        return data

    def save(self, **kwargs):
        self.instance = super().save(commit=False)
        self.instance.title = self.cleaned_data['title']
        if not hasattr(self.instance, 'author') or self.instance.author is None:
            self.instance.author = self.user
        self.instance.save()
        return self.instance
