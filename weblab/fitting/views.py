"""
Views for fitting specifications and results.

As far as possible these reuse code & templates from entities and experiments.

At present I'm not sure what the best way to do this is. Many of the forms & views will
be the same, but some will differ, and sometimes quite a long way in. So we may need to
create separate versions of everything (but reuse code & templates where possible). Or
we may be able to extend the base classes to be able to delegate to elsewhere, for instance
by removing the hardcoded 'entities:' namespace from reverse() calls.
"""

from braces.views import UserFormKwargsMixin, UserPassesTestMixin
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse
from django.views.generic import DetailView
from django.views.generic.edit import CreateView, FormMixin

from entities.views import EntityNewVersionView, EntityTypeMixin

from .forms import FittingSpecForm, FittingSpecVersionForm, FittingSpecRenameForm
from .models import FittingSpec


class FittingSpecCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, EntityTypeMixin,
    UserFormKwargsMixin, CreateView
):
    """Create a new fitting specification, initially without any versions."""
    template_name = 'entities/entity_form.html'
    permission_required = 'entities.create_fittingspec'
    form_class = FittingSpecForm

    def get_success_url(self):
        return reverse('fitting:newversion',
                       args=[self.kwargs['entity_type'], self.object.pk])


class FittingSpecNewVersionView(EntityNewVersionView):
    """Create a new version of a fitting specification.

    This is almost identical to other entities, except that we can't re-run experiments.
    """
    form_class = FittingSpecVersionForm


class RenameView(LoginRequiredMixin, UserFormKwargsMixin, UserPassesTestMixin, FormMixin, EntityTypeMixin, DetailView):
    template_name = 'entities/entity_rename_form.html'
    context_object_name = 'entity'

    @property
    def form_class(self):
        if self.model is FittingSpec:
            return FittingSpecRenameForm

    def _get_object(self):
        if not hasattr(self, 'object'):
            self.object = self.get_object()
        return self.object

    def test_func(self):
        return self._get_object().is_editable_by(self.request.user)

    def post(self, request, *args, **kwargs):
        """Check the form and possibly add the tag in the repo.

        Called by Django when a form is submitted.
        """
        form = self.get_form()

        if form.is_valid():
            new_name = form.cleaned_data['name']
            entity = self.get_object()
            entity.name = new_name
            entity.save()
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self):
        """What page to show when the form was processed OK."""
        entity = self.object
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':detail', args=[entity.url_type, entity.id])