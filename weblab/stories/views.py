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
    StoryPartFormSet,
)
from entities.models import ModelEntity, ModelGroup
from entities.views import EditCollaboratorsAbstractView
from experiments.models import Experiment
from .models import Story, StoryPart


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
    formset_class = StoryPartFormSet
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
                self.formset = self.formset_class(initial=initial,form_kwargs=form_kwargs)
        return self.formset

    def get_context_data(self, **kwargs):
        if 'formset' not in kwargs:
            kwargs['formset'] = self.get_formset()
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        formset = self.get_formset()
        if form.is_valid() and formset.is_valid():
            story = form.save()
            storyparts = formset.save(story=story)
            return self.form_valid(form)
        else:
            self.object = None
            return self.form_invalid(form)

