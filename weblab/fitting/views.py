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
from django.utils.text import get_valid_filename
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView

from core.visibility import VisibilityMixin
from datasets import views as dataset_views
from entities.views import EntityNewVersionView, EntityTypeMixin

from .forms import FittingSpecForm, FittingSpecVersionForm
from .models import FittingResult, FittingResultVersion


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


class FittingResultVersionListView(VisibilityMixin, DetailView):
    """Show all versions of a fitting result"""
    model = FittingResult
    context_object_name = 'fittingresult'
    template_name = 'fitting/fittingresult_versions.html'


class FittingResultVersionView(VisibilityMixin, DetailView):
    model = FittingResultVersion
    context_object_name = 'version'


class FittingResultVersionArchiveView(dataset_views.DatasetArchiveView):
    """
    Download a combine archive of an experiment version
    """
    model = FittingResultVersion

    def get_archive_name(self, version):
        return get_valid_filename('%s.zip' % version.fittingresult.name)
