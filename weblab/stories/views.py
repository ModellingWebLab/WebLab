from braces.views import UserFormKwargsMixin
from django.contrib import messages
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
from entities.models import ModelEntity, ModelGroup
from entities.views import EditCollaboratorsAbstractView
from experiments.models import Experiment, ExperimentVersion, ProtocolEntity, Runnable
from .models import Story, StoryText
import csv, io


class StoryListView(LoginRequiredMixin, ListView):
    """
    List all user's stories
    """
    template_name = 'stories/story_list.html'

    def get_queryset(self):
        return Story.objects.filter(
            id__in=[story.id for story in Story.objects.all() if story.is_editable_by(self.request.user)]
        )


class StoryView(LoginRequiredMixin, UserPassesTestMixin, UserFormKwargsMixin):
    """
    Base view for creating or editing stories
    """
    model = Story
    template_name = 'stories/story_form.html'

    @property
    def form_class(self):
        return StoryForm

    def get_success_url(self):
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':stories')


class StoryEditView(StoryView, UpdateView):
    """
    View for editing stories
    """

    def test_func(self):
        self.user = self.request.user
        return self.get_object().is_editable_by(self.request.user)


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
            othermodels = story.othermodels.all()
            modelgroups = story.modelgroups.all()
            experiments = story.experiments.all()
            visible_entities = ModelEntity.objects.visible_to_user(user)
            visible_model_groups = [m for m in ModelGroup.objects.all() if m.visible_to_user(user)]
            visible_experiments = [e for e in Experiment.objects.all() if e.is_visible_to_user(user)]
            if Story.objects.filter(title=story.title, author=user).exists():
                form.add_error(None, "User already has a story called %s" % (modelgroup.title))
                return self.form_invalid(form)
            if any (m not in visible_entities for m in othermodels):
                form.add_error(None, "User %s does not have access to all models in the model group" % (user.full_name))
                return self.form_invalid(form)
            if any (m not in visible_model_groups for m in modelgroups):
                form.add_error(None, "User %s does not have access to all model groups in the story" % (user.full_name))
                return self.form_invalid(form)
            if any (e not in visible_experiments for e in experiments):
                form.add_error(None, "User %s does not have access to all experiments in the story" % (user.full_name))
                return self.form_invalid(form)

            story.author = user
            story.save()
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self, *args, **kwargs):
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':stories')


class StoryCreateView(LoginRequiredMixin, UserPassesTestMixin, UserFormKwargsMixin, CreateView):
    """
    Create new model story
    """
    model = Story
    form_class = StoryForm
    formset_class = StoryTextFormSet
    formset_graph_class = StoryGraphFormSet
    initial = []

    def get_success_url(self):
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':stories')

    def test_func(self):
        return self.request.user.has_perm('entities.create_model')

    def get_formset(self):
        if not hasattr(self, 'formset') or self.formset is None:
            initial = []
            form_kwargs = {'user': self.request.user}
            if self.request.method == 'POST':
                self.formset = self.formset_class(
                    self.request.POST,
                    initial=initial,
                    form_kwargs=form_kwargs)
            else:
                self.formset = self.formset_class(initial=initial, form_kwargs=form_kwargs)
        return self.formset

    def get_formset_graph(self):
        if not hasattr(self, 'formsetgraph') or self.formsetgraph is None:
            initial = []
            form_kwargs = {'user': self.request.user}
            if self.request.method == 'POST':
                self.formsetgraph = self.formset_graph_class(
                    self.request.POST,
                    initial=initial,
                    form_kwargs=form_kwargs)
            else:
                self.formsetgraph = self.formset_graph_class(initial=initial, form_kwargs=form_kwargs)
        return self.formsetgraph

    def get_context_data(self, **kwargs):
        if 'formset' not in kwargs:
            kwargs['formset'] = self.get_formset()
        if 'formsetgraph' not in kwargs:
            kwargs['formsetgraph'] = self.get_formset_graph()
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        formset = self.get_formset()
        if form.is_valid() and formset.is_valid():
            #make sure formsets are ordered correctly starting at 0
            for order, frm in enumerate(sorted(formset.ordered_forms, key=lambda f: f.order)):
                frm.cleaned_data['order'] = order

            story = form.save()
            storytexts = formset.save(story=story)
            return self.form_valid(form)
        else:
            self.object = None
            return self.form_invalid(form)


class StoryFilterModelOrGroupView(LoginRequiredMixin, ListView):
    model = ModelGroup
    template_name = 'stories/modelorgroup_selection.html'

    def get_queryset(self):
        qs=[{'pk': None, 'title': '--------- model group'}] +\
           [{'pk': 'modelgroup' + str(modelgroup.pk), 'title': modelgroup.title} for modelgroup in ModelGroup.objects.all() if modelgroup.visible_to_user(self.request.user)] +\
           [{'pk': None, 'title': '--------- model'}] +\
           [{'pk': 'model' + str(model.pk), 'title': model.name} for model in ModelEntity.objects.visible_to_user(self.request.user)]
        return qs


class StoryFilterProtocolView(LoginRequiredMixin, ListView):
    model = ProtocolEntity
    template_name = 'stories/protocolentity_selection.html'

    def get_queryset(self):
        mk = self.kwargs['mk']
        if mk.startswith('modelgroup'):
            mk = int(mk.replace('modelgroup',''))
            models = ModelGroup.objects.get(pk=mk).models.all()
        else:
            mk = int(mk.replace('model',''))
            models = ModelEntity.objects.filter(pk=mk)

        # Get protocols for whcih the latest result run succesful
        # that users can see for the model(s) we're looking at
        return set(e.protocol for e in Experiment.objects.all()
                   if e.latest_result == Runnable.STATUS_SUCCESS and
                   e.is_visible_to_user(self.request.user)
                   and e.model in models)


class StoryFilterGraphView(LoginRequiredMixin, ListView):
    model = ExperimentVersion
    template_name = 'stories/graph_selection.html'

    def get_queryset(self):
        mk = self.kwargs['mk']
        pk = self.kwargs['pk']
        protocol = ProtocolEntity,objects.get(pk=pk)
        if mk.startswith('modelgroup'):
            mk = int(mk.replace('modelgroup',''))
            models = ModelGroup.objects.get(pk=mk).models.all()
        else:
            mk = int(mk.replace('model',''))
            models = ModelEntity.objects.filter(pk=mk)


        experimentversions = [e.latest_versionl for e in Experiment.objects.filter(protocol=protocol, model__in=models)
                              if e.latest_result == Runnable.STATUS_SUCCESS and
                              e.is_visible_to_user(self.request.user)
                              and e.model in models]

        files = set()
        for experimentver in experimentversions:
            # find outputs-contents.csv
            try:
                plots_data_file = experimentver.open_file('outputs-default-plots.csv').read().decode("utf-8")
                plots_data_stream = io.StringIO(plots_data_file)
                for row in csv.DictReader(plots_data_stream):
                    files.add(row['Data file name'])
            except FileNotFoundError:
                pass  #  This experiemnt version has no graphs
        return files

