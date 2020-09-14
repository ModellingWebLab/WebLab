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
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.urls import reverse
from django.utils.text import get_valid_filename
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, FormView

from core.visibility import VisibilityMixin
from datasets import views as dataset_views
from entities.views import EntityNewVersionView, EntityTypeMixin

from .forms import FittingResultCreateForm, FittingSpecForm, FittingSpecVersionForm
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
    Download a combine archive of a fitting result version
    """
    model = FittingResultVersion

    def get_archive_name(self, version):
        return get_valid_filename('%s.zip' % version.fittingresult.name)


class FittingResultFileDownloadView(dataset_views.DatasetFileDownloadView):
    """
    Download an individual file from a fitting result
    """
    model = FittingResultVersion


class FittingResultVersionJsonView(VisibilityMixin, SingleObjectMixin, View):
    """
    Serve up json view of a fitting result verson
    """
    model = FittingResultVersion

    def get(self, request, *args, **kwargs):
        version = self.get_object()
        ns = self.request.resolver_match.namespace
        url_args = [version.fittingresult.id, version.id]
        details = version.get_json(ns, url_args)
        details.update({
            'status': version.status,
            'version': version.id,
            'fittingResultId': version.fittingresult.id,
        })
        return JsonResponse({
            'version': details,
        })


class FittingResultDeleteView(dataset_views.DatasetDeleteView):
    """
    Delete all versions of a fitting result
    """
    model = FittingResult

    def get_success_url(self, *args, **kwargs):
        return reverse('experiments:list') + '?show_fits=true'


class FittingResultVersionDeleteView(dataset_views.DatasetDeleteView):
    """
    Delete a single version of a fitting result
    """
    model = FittingResultVersion

    def get_success_url(self, *args, **kwargs):
        return reverse('fitting:result:versions', args=[self.get_object().fittingresult.id])


class FittingResultComparisonView(TemplateView):
    """
    Compare multiple fitting result versions
    """
    template_name = 'fitting/fittingresultversion_compare.html'

    def get_context_data(self, **kwargs):
        pks = set(map(int, self.kwargs['version_pks'].strip('/').split('/')))
        versions = FittingResultVersion.objects.filter(pk__in=pks).order_by('created_at')
        versions = [v for v in versions if v.fittingresult.is_visible_to_user(self.request.user)]

        if len(versions) < len(pks):
            messages.error(
                self.request,
                'Some requested fitting results could not be found '
                '(or you don\'t have permission to see them)'
            )

        kwargs.update({
            'fittingresult_versions': versions,
        })
        return super().get_context_data(**kwargs)


class FittingResultComparisonJsonView(View):
    """
    Serve up JSON view of multiple fitting result versions for comparison
    """
    def _version_json(self, version, model_version_in_name, protocol_version_in_name):
        """
        JSON for a single fitting result version

        :param version: FittingResultVersion object
        :param model_version_in_name: Whether to include model version specifier in name field
        :param protocol_version_in_name: Whether to include protocol version specifier in name field
        """
        exp = version.fittingresult
        ns = self.request.resolver_match.namespace
        url_args = [exp.id, version.id]
        details = version.get_json(ns, url_args)
        details.update({
            'name': exp.name,
            'url': reverse(ns + ':version', args=url_args),
            'versionId': version.id,
            'modelName': exp.model.name,
            'protoName': exp.protocol.name,
            'fittingSpecName': exp.fittingspec.name,
            'datasetName': exp.dataset.name,
            'modelVersion': exp.model_version.get_name(),
            'protoVersion': exp.protocol_version.get_name(),
            'fittingSpecVersion': exp.fittingspec_version.get_name(),
            'runNumber': version.run_number,
        })
        return details

    def get(self, request, *args, **kwargs):
        pks = {int(pk) for pk in self.kwargs['version_pks'][1:].split('/') if pk}
        versions = FittingResultVersion.objects.filter(pk__in=pks).order_by('created_at')
        versions = [v for v in versions if v.fittingresult.is_visible_to_user(self.request.user)]

        models = set((v.fittingresult.model, v.fittingresult.model_version) for v in versions)
        protocols = set((v.fittingresult.protocol, v.fittingresult.protocol_version) for v in versions)
        compare_model_versions = len(models) > len(dict(models))
        compare_protocol_versions = len(protocols) > len(dict(protocols))

        response = {}
        response = {
            'getEntityInfos': {
                'entities': [
                    self._version_json(version, compare_model_versions, compare_protocol_versions)
                    for version in versions
                ]
            }
        }

        return JsonResponse(response)


class FittingResultCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    permission_required = 'fitting.run_fits'
    form_class = FittingResultCreateForm

    template_name = 'fitting/fittingresult_create_form.html'
