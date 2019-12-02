"""
Views for fitting specifications and results.

As far as possible these reuse code & templates from entities and experiments.

At present I'm not sure what the best way to do this is. Many of the forms & views will
be the same, but some will differ, and sometimes quite a long way in. So we may need to
create separate versions of everything (but reuse code & templates where possible). Or
we may be able to extend the base classes to be able to delegate to elsewhere, for instance
by removing the hardcoded 'entities:' namespace from reverse() calls.
"""

from braces.views import UserFormKwargsMixin
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView

from .forms import FittingSpecForm
from .models import FittingSpec


class FittingSpecMixin:
    """
    Mixin for entity-style pages, setting the entity type to be a fitting specification.
    """
    model = FittingSpec
    other_model = None

    def get_context_data(self, **kwargs):
        kwargs.update({
            'entity_type': self.model.entity_type,
            'other_type': self.model.other_type,
            'type': self.model.display_type,
            'url_type': self.model.url_type,
        })
        return super().get_context_data(**kwargs)


class FittingSpecCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FittingSpecMixin,
    UserFormKwargsMixin, CreateView
):
    """Create a new fitting specification, initially without any versions."""
    template_name = 'entities/entity_form.html'
    permission_required = 'entities.create_fittingspec'
    form_class = FittingSpecForm

    def get_success_url(self):
        return reverse('fitting:newspecversion',
                       args=[self.object.pk])


class FittingSpecListView(LoginRequiredMixin, FittingSpecMixin, ListView):
    """
    List all user's fitting specifications.
    """
    template_name = 'entities/entity_list.html'

    def get_queryset(self):
        return self.model.objects.filter(author=self.request.user)
