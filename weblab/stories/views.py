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
                    prefix='text',
                    initial=initial,
                    form_kwargs=form_kwargs)
            else:
                self.formset = self.formset_class(prefix='text', initial=initial, form_kwargs=form_kwargs)
        return self.formset

    def get_formset_graph(self):
        if not hasattr(self, 'formsetgraph') or self.formsetgraph is None:
            initial = []
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
        if 'formset' not in kwargs:
            kwargs['formset'] = self.get_formset()
        if 'formsetgraph' not in kwargs:
            kwargs['formsetgraph'] = self.get_formset_graph()
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        formset = self.get_formset()
        formsetgraph = self.get_formset_graph()
        if form.is_valid() and formset.is_valid() and formsetgraph.is_valid():
            #make sure formsets are ordered correctly starting at 0
            for order, frm in enumerate(sorted(formset.ordered_forms + formsetgraph.ordered_forms, key=lambda f: f.cleaned_data['ORDER'])):
                frm.cleaned_data['ORDER'] = order

            story = form.save()
            formset.save(story=story)
            formsetgraph.save(story=story)
            return self.form_valid(form)
        else:
            self.object = None
            return self.form_invalid(form)


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
        models=[]
        if mk.startswith('modelgroup'):
            mk = int(mk.replace('modelgroup',''))
            models = ModelGroup.objects.get(pk=mk).models.all()
        elif mk.startswith('model'):
            mk = int(mk.replace('model',''))
            models = ModelEntity.objects.filter(pk=mk)
        else:
            return []

        # Get protocols for which the latest result run succesful
        # that users can see for the model(s) we're looking at
        return StoryGraphFormSet.get_protocol_choices(self.request.user, models=models)


class StoryFilterGraphView(LoginRequiredMixin, ListView):
    model = ExperimentVersion
    template_name = 'stories/graph_selection.html'

    def get_queryset(self):
        mk = self.kwargs.get('mk', '')
        pk = self.kwargs.get('pk', '')
        models=[]
        if pk == '':
            return []
        if mk.startswith('modelgroup'):
            mk = int(mk.replace('modelgroup',''))
            models = ModelGroup.objects.get(pk=mk).models.all()
        elif mk.startswith('model'):
            mk = int(mk.replace('model',''))
            models = ModelEntity.objects.filter(pk=mk)
        else:
            return []

        protocol = ProtocolEntity.objects.get(pk=pk)
        return StoryGraphFormSet.get_graph_choices(self.request.user, protocol=protocol, models=models)
