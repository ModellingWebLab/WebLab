import csv
import io
import re
from collections import OrderedDict

from braces.views import UserFormKwargsMixin
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse
from django.views.generic.detail import DetailView
from django.views.generic.edit import (
    CreateView,
    DeleteView,
    FormMixin,
    UpdateView,
)
from django.views.generic.list import ListView

from accounts.forms import OwnershipTransferForm
from entities.models import ModelEntity, ModelGroup, ProtocolEntity
from entities.views import EditCollaboratorsAbstractView
from experiments.models import Experiment, ExperimentVersion, Runnable
from repocache.models import CachedModelVersion, CachedProtocolVersion

from .forms import (
    StoryCollaboratorFormSet,
    StoryForm,
    StoryGraphFormSet,
    StoryTextFormSet,
)
from .models import Story, StoryGraph, StoryText


def get_experiment_versions(user, cachedprotocolversion, cachedmodelversion_pks):
    """Retreives the experiment versions relating to a user, model(group) version and protocol version combination. """
    return [e.latest_version for e in Experiment.objects.filter(model_version__pk__in=cachedmodelversion_pks,
                                                                protocol_version=cachedprotocolversion)
            if e.latest_result == Runnable.STATUS_SUCCESS and e.is_visible_to_user(user)]


def get_url(experiment_versions):
    """Returns formatted experiment versions t use in a url """
    return '/' + '/'.join(str(ver.pk) for ver in experiment_versions)

def get_versions_for_model_and_protocol(user, mk, pk):
    """Retreives the experiment versions relating to a user, model(group) and protocol combination. """
    if not pk or not mk:
        return []

    protocol_version = ProtocolEntity.objects.get(pk=pk).repocache.latest_version.pk
    if mk.startswith('modelgroup'):
        mk = int(mk.replace('modelgroup', ''))
        model_version_pks = [m.repocache.latest_version.pk
                             for m in ModelGroup.objects.get(pk=mk).models.all()
                             if m.repocache.versions.count()]
    else:
        assert mk.startswith('model'), "The model of group field value should start with model or modelgroup."
        mk = int(mk.replace('model', ''))
        model_version_pks = [ModelEntity.objects.get(pk=mk).repocache.latest_version.pk]
    return get_experiment_versions(user, protocol_version, model_version_pks)

def get_graph_file_names(user, mk, pk):
    """Retreives the file names of graphs for a given user, model(group) and protocol."""
    experiment_versions = get_versions_for_model_and_protocol(user, mk, pk)
    graph_files = OrderedDict()
    for experimentver in experiment_versions:
        try:
            plots_data_file = experimentver.open_file('outputs-default-plots.csv').read().decode("utf-8")
            plots_data_stream = io.StringIO(plots_data_file)
            for row in csv.DictReader(plots_data_stream):
                graph_files[(row['Data file name'], row['Data file name'])] = True
        except (FileNotFoundError, KeyError):
            pass  # This experiemnt version has no graphs
    return graph_files.keys()

def get_modelgroups(user):
    """ Returns the available model(group)s for a given user."""
    return [('', '--------- model group')] +\
           [('modelgroup' + str(modelgroup.pk), modelgroup.title) for modelgroup in ModelGroup.objects.all()
            if modelgroup.visible_to_user(user)] +\
           [('', '--------- model')] +\
           [('model' + str(model.pk), model.name)
            for model in ModelEntity.objects.visible_to_user(user)
            if model.repocache.versions.count()]


def get_protocols(mk, user):
    """ Returns the available protocols for given user and model(group)."""
    if mk.startswith('modelgroup'):
        mk = int(mk.replace('modelgroup', ''))
        models = ModelGroup.objects.get(pk=mk).models.all()
    elif mk.startswith('model'):
        mk = int(mk.replace('model', ''))
        models = ModelEntity.objects.filter(pk=mk)
    else:
        return []

    selected_model_pks = models.values_list('pk', flat=True)
    latest_model_versions_visible_pk = CachedModelVersion.objects.visible_to_user(user) \
                                                                 .order_by('entity', '-timestamp') \
                                                                 .values_list('pk', flat=True) \
                                                                 .distinct('entity')

    latest_protocol_versions_visible_pks = CachedProtocolVersion.objects.visible_to_user(user) \
                                                                .order_by('entity', '-timestamp') \
                                                                .values_list('pk', flat=True) \
                                                                .distinct('entity')

    succesful_experiment_pks = ExperimentVersion.objects.filter(status=Runnable.STATUS_SUCCESS) \
                                                .prefetch_related('experiment__pk') \
                                                .values_list('experiment__pk', flat=True)

    experiments = Experiment.objects.filter(pk__in=succesful_experiment_pks,
                                            model__pk__in=selected_model_pks,
                                            model_version__pk__in=latest_model_versions_visible_pk,
                                            protocol_version__pk__in=latest_protocol_versions_visible_pks) \
                                    .prefetch_related('protocol, protocol__pk, protocol__name')

    return experiments.order_by('protocol__pk').values_list('protocol__pk', 'protocol__name', flat=False).distinct()



class StoryListView(ListView):
    """
    List all user's stories
    """
    template_name = 'stories/story_list.html'

    def get_queryset(self):
        return Story.objects.filter(
            id__in=[story.id for story in Story.objects.all() if story.visible_to_user(self.request.user)]
        )


class StoryDeleteView(UserPassesTestMixin, DeleteView):
    """
    Delete a story
    """
    model = Story
    # Raise a 403 error rather than redirecting to login,
    # if the user doesn't have delete permissions.
    raise_exception = True

    def test_func(self):
        return self.get_object().is_deletable_by(self.request.user)

    def get_success_url(self, *args, **kwargs):
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':stories')


class StoryCollaboratorsView(EditCollaboratorsAbstractView):
    """
    Edit collaborators for stories
    """
    model = Story
    context_object_name = 'story'
    template_name = 'stories/story_collaborators_form.html'
    formset_class = StoryCollaboratorFormSet

    def get_success_url(self):
        """What page to show when the form was processed OK."""
        entity = self.object
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':story_collaborators', args=[entity.id])


class StoryTransferView(LoginRequiredMixin, UserPassesTestMixin,
                        FormMixin, DetailView):
    model = Story
    template_name = 'stories/story_transfer_ownership.html'
    context_object_name = 'story'
    form_class = OwnershipTransferForm

    def test_func(self):
        self.object = self.get_object()
        return self.object.is_managed_by(self.request.user)

    def post(self, request, *args, **kwargs):
        """Check the form and transfer ownership of the entity.

        Called by Django when a form is submitted.
        """
        form = self.get_form()

        if form.is_valid():
            user = form.cleaned_data['user']
            story = self.get_object()
            graphs = StoryGraph.objects.filter(story=story)
            model_versions = [mv for sublist in [graph.cachedmodelversions.all() for graph in graphs] for mv in sublist]

            visible_model_groups = [m for m in ModelGroup.objects.all() if m.visible_to_user(user)]

            if Story.objects.filter(title=story.title, author=user).exists():
                form.add_error(None, "User %s already has a story called %s" % (user.full_name, story.title))
                return self.form_invalid(form)

            if any(graph.modelgroup is not None and graph.modelgroup not in visible_model_groups for graph in graphs):
                form.add_error(None, "User %s does not have access to all graph's model groups" % (user.full_name))
                return self.form_invalid(form)

            if not all(graph.cachedprotocolversion.protocol.is_version_visible_to_user(graph.cachedprotocolversion.sha,
                                                                                       user) for graph in graphs):
                form.add_error(None, "User %s does not have access to (current version of) protocol" % (user.full_name))
                return self.form_invalid(form)

            if not all(mv.model.is_version_visible_to_user(mv.sha, user) for mv in model_versions):
                form.add_error(None, "User %s does not have access to all model versions in the story" %
                               (user.full_name))
                return self.form_invalid(form)

            story.author = user
            story.save()
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self, *args, **kwargs):
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':stories')


class StoryView(LoginRequiredMixin, UserPassesTestMixin, UserFormKwargsMixin):
    """
    Create new model story
    """
    model = Story
    form_class = StoryForm
    formset_class = StoryTextFormSet
    formset_graph_class = StoryGraphFormSet

    def get_success_url(self):
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':stories')

    def get_formset(self, initial=[{'ORDER': ''}]):
        if not hasattr(self, 'formset') or self.formset is None:
            form_kwargs = {'user': self.request.user}
            if self.request.method == 'POST':
                self.formset = self.formset_class(
                    self.request.POST,
                    prefix='text',
                    initial=initial,
                    form_kwargs=form_kwargs)
            else:
                self.formset = self.formset_class(prefix='text', initial=initial, form_kwargs=form_kwargs)
        return self.formset

    def get_formset_graph(self, initial=[{'ORDER': '', 'currentGraph': '', 'experimentVersions': ''}]):
        if not hasattr(self, 'formsetgraph') or self.formsetgraph is None:
            form_kwargs = {'user': self.request.user}
            if self.request.method == 'POST':
                self.formsetgraph = self.formset_graph_class(
                    self.request.POST,
                    prefix='graph',
                    initial=initial,
                    form_kwargs=form_kwargs)
            else:
                self.formsetgraph = self.formset_graph_class(prefix='graph', initial=initial, form_kwargs=form_kwargs)
        return self.formsetgraph

    def get_context_data(self, **kwargs):
        # get base uri, to use for graph previews
        ns = self.request.resolver_match.namespace
        absolute_uri = self.request.build_absolute_uri()
        kwargs['base_uri'] = re.sub('/' + ns + '/.*', '', absolute_uri)
        kwargs['formset'] = self.get_formset()
        kwargs['formsetgraph'] = self.get_formset_graph()
        kwargs['storyparts'] = sorted(list(kwargs['formset']) + list(kwargs['formsetgraph']), key=lambda f: f['ORDER'].value())
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        formset = self.get_formset()
        formsetgraph = self.get_formset_graph()
        form.num_parts = 1
        if formset.is_valid() and formsetgraph.is_valid():
            form.num_parts = len(formset.ordered_forms) + len(formsetgraph.ordered_forms)
            if form.is_valid():
                story = form.save()
                formset.save(story=story)
                formsetgraph.save(story=story)
                return self.form_valid(form)
        self.object = getattr(self, 'object', None)
        return self.form_invalid(form)


class StoryCreateView(StoryView, CreateView):
    """
    View for creating new stories
    """
    def test_func(self):
        return self.request.user.has_perm('entities.create_model')


class StoryEditView(StoryView, UpdateView):
    model = Story
    template_name = 'stories/story_edit.html'
    context_object_name = 'story'

    def test_func(self):
        self.object = self.get_object()
        return self.get_object().is_editable_by(self.request.user)

    def get_formset(self):
        return super().get_formset(initial=[{'number': i,
                                             'description': s.description,
                                             'ORDER': s.order,
                                             'pk': s.pk}
                                            for i, s in enumerate(StoryText.objects.filter(story=self.object))])
    def get_formset_graph(self):
        modelgroupselectors = get_modelgroups(self.request.user)
        initial = []
        for i, s in enumerate(StoryGraph.objects.filter(story=self.object)):
            experimentVersions = get_url(get_experiment_versions(s.author,
                                                                 s.cachedprotocolversion,
                                                                 [v.pk for v in s.cachedmodelversions.all()]))
            initial.append(
                {'number': i,
                 'models_or_group': 'modelgroup' + str(s.modelgroup.pk) if s.modelgroup is not None else 'model' + str(s.cachedmodelversions.first().model.pk),
                 'protocol': s.cachedprotocolversion.protocol.pk,
                 'graphfilename': s.graphfilename,
                 'graphfiles': s.graphfilename,
                 'currentGraph': str(s),
                 'experimentVersionsUpdate': experimentVersions,
                 'experimentVersions': experimentVersions,
                 'ORDER': s.order,
                 'update': False,
                 'pk': s.pk}
            )
        return super().get_formset_graph(initial=initial)


class StoryFilterModelOrGroupView(LoginRequiredMixin, ListView):
    model = ModelGroup
    template_name = 'stories/modelorgroup_selection.html'

    def get_queryset(self):
        return get_modelgroups(self.request.user)


class StoryFilterProtocolView(LoginRequiredMixin, ListView):
    model = ProtocolEntity
    template_name = 'stories/protocolentity_selection.html'

    def get_queryset(self):
        mk = self.kwargs.get('mk', '')
        return get_protocols(mk, self.request.user)


class StoryFilterExperimentVersions(LoginRequiredMixin, ListView):
    model = ExperimentVersion
    template_name = 'stories/experiment_versions.html'

    def get_queryset(self):
        return get_url(get_versions_for_model_and_protocol(self.request.user, self.kwargs.get('mk', ''), self.kwargs.get('pk', '')))


class StoryFilterGraphView(LoginRequiredMixin, ListView):
    model = ExperimentVersion
    template_name = 'stories/graph_selection.html'

    def get_queryset(self):
        return get_graph_file_names(self.request.user, self.kwargs.get('mk', ''), self.kwargs.get('pk', ''))


class StoryRenderView(UserPassesTestMixin, DetailView):
    model = Story
    template_name = 'stories/story_render.html'
    context_object_name = 'story'

    def test_func(self):
        return self.get_object().visible_to_user(self.request.user)

    def get_context_data(self, **kwargs):
        # rendering markdown client side vie marked: https://marked.js.org/)

        kwargs['storyparts'] = sorted([text for text in StoryText.objects.filter(story=self.get_object())] +
                                      [graph for graph in StoryGraph.objects.filter(story=self.get_object())],
                                      key=lambda f: f.order)
        for part in kwargs['storyparts']:
            if isinstance(part, StoryGraph):
                part.experiment_versions = get_url(
                    get_experiment_versions(self.request.user,
                                            part.cachedprotocolversion,
                                            [v.pk for v in part.cachedmodelversions.all()]))
        return super().get_context_data(**kwargs)
