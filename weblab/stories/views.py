from braces.views import UserFormKwargsMixin
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
)

from django.urls import reverse
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, DeleteView, FormMixin, UpdateView
from django.views.generic.list import ListView

from accounts.forms import OwnershipTransferForm

from .forms import (
    StoryCollaboratorFormSet,
    StoryForm,
    StoryTextFormSet,
    StoryGraphFormSet,
)
from entities.models import ModelGroup
from entities.views import EditCollaboratorsAbstractView
from experiments.models import Experiment, ExperimentVersion, ProtocolEntity, Runnable
from .models import Story, StoryText, StoryGraph
from repocache.models import CachedProtocolVersion, CachedModelVersion


def get_experiment_versions_url(user, cachedprotocolversion, cachedmodelversions):
    experiment_versions = [e.latest_version.id for e in Experiment.objects.all()
                           if e.latest_result == Runnable.STATUS_SUCCESS and
                           e.is_visible_to_user(user) and
                           e.protocol_version == cachedprotocolversion
                           and e.model_version in cachedmodelversions]
    return '/' + '/'.join(str(ver) for ver in experiment_versions)


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
        kwargs['formset'] = self.get_formset()
        kwargs['formsetgraph'] = self.get_formset_graph()
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        formset = self.get_formset()
        formsetgraph = self.get_formset_graph()
        if form.is_valid() and formset.is_valid() and formsetgraph.is_valid():
            if len(formset.ordered_forms + formsetgraph.ordered_forms) == 0:
                form.add_error(
                    None,
                    "Story is empty add at least one text box or graph. "
                )
                self.object = None
                return self.form_invalid(form)

            # make sure formsets are ordered correctly starting at 0
            for order, frm in enumerate(sorted(formset.ordered_forms + formsetgraph.ordered_forms,
                                               key=lambda f: f.cleaned_data['ORDER'])):
                frm.cleaned_data['ORDER'] = order
            story = form.save()
            formset.save(story=story)
            formsetgraph.save(story=story)
            return self.form_valid(form)
        else:
            self.object = getattr(self, 'object', None)
            return self.form_invalid(form)


class StoryCreateView(StoryView, CreateView):
    """
    View for creating new stories
    """
    def test_func(self):
        return self.request.user.has_perm('entities.create_model')


class StoryEditView(StoryView, UpdateView):
    """
    View for editing stories
    """
    def test_func(self):
        self.object = self.get_object()
        return self.get_object().is_editable_by(self.request.user)

    def get_formset(self):
        initial = [{'description': s.description,
                    'ORDER': s.order,
                    'pk': s.pk} for s in StoryText.objects.filter(story=self.object)]
        return super().get_formset(initial=initial)

    def get_formset_graph(self):
        initial = [{'models_or_group': 'modelgroup' + str(s.modelgroup.pk)
                    if s.modelgroup is not None else 'model' + str(s.cachedmodelversions.first().pk),
                    'protocol': s.cachedprotocolversion.pk,
                    'graphfiles': s.graphfilename,
                    'currentGraph': str(s),
                    'experimentVersions': get_experiment_versions_url(s.author,
                                                                      s.cachedprotocolversion,
                                                                      s.cachedmodelversions.all()),
                    'ORDER': s.order,
                    'pk': s.pk} for s in StoryGraph.objects.filter(story=self.object)]
        return super().get_formset_graph(initial=initial)


class StoryFilterModelOrGroupView(LoginRequiredMixin, ListView):
    model = ModelGroup
    template_name = 'stories/modelorgroup_selection.html'

    def get_queryset(self):
        return StoryGraphFormSet.get_modelgroup_choices(self.request.user)


class StoryFilterProtocolView(LoginRequiredMixin, ListView):
    model = ProtocolEntity
    template_name = 'stories/protocolentity_selection.html'

    def get_queryset(self):
        mk = self.kwargs.get('mk', '')
        if mk.startswith('modelgroup'):
            mk = int(mk.replace('modelgroup', ''))
            model_versions = [m.repocache.latest_version for m in ModelGroup.objects.get(pk=mk).models.all()
                              if m.repocache.versions.count()]
        elif mk.startswith('model'):
            mk = int(mk.replace('model', ''))
            model_versions = CachedModelVersion.objects.filter(pk=mk)
        else:
            return []

        # Get protocols for which the latest result run succesful
        # that users can see for the model(s) we're looking at
        return StoryGraphFormSet.get_protocol_choices(self.request.user, model_versions=model_versions)


class StoryFilterGraphView(LoginRequiredMixin, ListView):
    model = ExperimentVersion
    template_name = 'stories/graph_selection.html'

    def get_queryset(self):
        mk = self.kwargs.get('mk', '')
        pk = self.kwargs.get('pk', '')
        model_versions = []
        if pk == '':
            return []
        if mk.startswith('modelgroup'):
            mk = int(mk.replace('modelgroup', ''))
            model_versions = [m.repocache.latest_version for m in ModelGroup.objects.get(pk=mk).models.all()
                              if m.repocache.versions.count()]
        else:
            assert mk.startswith('model'), "The model of group field value should start with model or modelgroup."
            mk = int(mk.replace('model', ''))
            model_versions = CachedModelVersion.objects.filter(pk=mk)
        protocol_version = CachedProtocolVersion.objects.get(pk=pk)
        return StoryGraphFormSet.get_graph_choices(self.request.user, protocol_version=protocol_version,
                                                   model_versions=model_versions)


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
                part.experiment_versions = get_experiment_versions_url(self.request.user,
                                                                       part.cachedprotocolversion,
                                                                       part.cachedmodelversions.all())
        return super().get_context_data(**kwargs)
