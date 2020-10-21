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
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F, Q
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.text import get_valid_filename
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, FormView

from core.visibility import VisibilityMixin
from datasets import views as dataset_views
from datasets.models import Dataset
from entities.models import ModelEntity, ProtocolEntity
from entities.views import EntityNewVersionView, EntityTypeMixin, RenameView
from experiments.views import ExperimentMatrixJsonView
from repocache.models import CachedFittingSpecVersion, CachedModelVersion, CachedProtocolVersion

from .forms import (
    FittingResultCreateForm,
    FittingSpecForm,
    FittingSpecRenameForm,
    FittingSpecVersionForm,
)
from .models import FittingResult, FittingResultVersion, FittingSpec
from .processing import submit_fitting


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


class FittingSpecRenameView(RenameView):
    """Rename a fitting specification."""
    form_class = FittingSpecRenameForm


class FittingSpecResultsMatrixView(EntityTypeMixin, DetailView):
    template_name = 'fitting/fittingspec_results_matrix.html'

    def get_queryset(self):
        return FittingSpec.objects.visible_to_user(self.request.user)


class FittingSpecResultsMatrixJsonView(SingleObjectMixin, ExperimentMatrixJsonView):
    def get_queryset(self):
        return FittingSpec.objects.visible_to_user(self.request.user)

    @classmethod
    def dataset_json(cls, dataset):
        _json = {
            'id': dataset.id,
            'entityId': dataset.id,
            'author': dataset.author.get_full_name(),
            'visibility': dataset.visibility,
            'created': dataset.created_at,
            'name': dataset.name,
            'protocolId': dataset.protocol.id,
            'protocolLatestVersion': dataset.protocol.repocache.latest_version.sha,
            'url': reverse('datasets:detail', args=[dataset.id]),
        }

        return _json

    @classmethod
    def fittingresult_version_json(cls, version):
        return {
            'id': version.id,
            'entity_id': version.fittingresult.id,
            'latestResult': version.status,
            'dataset': cls.dataset_json(version.fittingresult.dataset),
            'model': cls.entity_json(
                version.fittingresult.model, version.fittingresult.model_version.sha,
                extend_name=True, visibility=version.model_visibility, author=version.model_author,
            ),
            'url': reverse(
                'fitting:result:version',
                args=[version.fittingresult.id, version.id]
            ),
        }

    def get(self, request, *args, **kwargs):
        spec = self.get_object()

        model_versions = None

        # Base models/protocols to show
        q_models = ModelEntity.objects.all()
        q_datasets = Dataset.objects.all()

        visibility_where = ~Q(visibility='private')

        # If specific versions have been requested, show at most those
        q_model_versions = self.versions_query('model', model_versions, q_models, visibility_where)

        # Get the JSON data needed to display the matrix axes
        model_versions = [self.entity_json(version.entity.entity, version.sha,
                                           extend_name=bool(model_versions),
                                           visibility=version.visibility,
                                           author=version.author_name,
                                           friendly_version=version.friendly_name)
                          for version in q_model_versions]
        model_versions = {ver['id']: ver for ver in model_versions}

        datasets = {ds.id: self.dataset_json(ds) for ds in q_datasets}

        # Only give info on fittingresults involving the correct entity versions
        fittingresults = {}
        q_fittings = FittingResult.objects.filter(
            model__in=q_models,
            model_version__in=q_model_versions,
            dataset__in=q_datasets,
        )
        q_fittingresult_versions = FittingResultVersion.objects.filter(
            fittingresult__in=q_fittings,
        ).order_by(
            'fittingresult__id',
            '-created_at',
        ).distinct(
            'fittingresult__id'
        ).select_related(
            'fittingresult',
            'fittingresult__model',
            'fittingresult__model__cachedmodel',
            'fittingresult__protocol',
            'fittingresult__dataset',
        ).annotate(
            dataset_visibility=F('fittingresult__dataset__visibility'),
            model_visibility=F('fittingresult__model_version__visibility'),
            dataset_author=F('fittingresult__dataset__author__full_name'),
            model_author=F('fittingresult__model__author__full_name'),
        )

        for fit_ver in q_fittingresult_versions:
            fittingresults[fit_ver.fittingresult.pk] = self.fittingresult_version_json(fit_ver)

        return JsonResponse({
            'getMatrix': {
                'models': model_versions,
                'columns': datasets,
                'experiments':  fittingresults
            }
        })


class FittingResultVersionListView(VisibilityMixin, DetailView):
    """Show all versions of a fitting result"""
    model = FittingResult
    context_object_name = 'fittingresult'
    template_name = 'fitting/fittingresult_versions.html'


class FittingResultVersionView(VisibilityMixin, DetailView):
    """Show a version of a fitting result"""
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


class FittingResultCreateView(LoginRequiredMixin, PermissionRequiredMixin, UserFormKwargsMixin, FormView):
    """
    Create and submit a fitting result from models, protocols, fitting specs and datasets
    and (where relevant) their versions.
    """
    permission_required = 'fitting.run_fits'
    form_class = FittingResultCreateForm

    template_name = 'fitting/fittingresult_create_form.html'

    def get_initial(self):
        initial = super().get_initial()
        model_id = self.request.GET.get('model')
        model_version = self.request.GET.get('model_version')
        protocol_id = self.request.GET.get('protocol')
        protocol_version = self.request.GET.get('protocol_version')
        fittingspec_id = self.request.GET.get('fittingspec')
        fittingspec_version = self.request.GET.get('fittingspec_version')
        dataset_id = self.request.GET.get('dataset')

        def get_version_query(version):
            if len(version) == 40:
                return {'sha': version}
            else:
                return {'id': version}

        if model_version:
            initial['model_version'] = get_object_or_404(
                CachedModelVersion.objects.visible_to_user(self.request.user),
                **get_version_query(model_version))
            initial['model'] = initial['model_version'].model
        elif model_id:
            initial['model'] = get_object_or_404(
                ModelEntity.objects.visible_to_user(self.request.user),
                pk=model_id)

        if protocol_version:
            initial['protocol_version'] = get_object_or_404(
                CachedProtocolVersion.objects.visible_to_user(self.request.user),
                **get_version_query(protocol_version))
            initial['protocol'] = initial['protocol_version'].protocol
        elif protocol_id:
            initial['protocol'] = get_object_or_404(
                ProtocolEntity.objects.visible_to_user(self.request.user),
                pk=protocol_id)

        if fittingspec_version:
            initial['fittingspec_version'] = get_object_or_404(
                CachedFittingSpecVersion.objects.visible_to_user(self.request.user),
                **get_version_query(fittingspec_version))
            initial['fittingspec'] = initial['fittingspec_version'].fittingspec
        elif fittingspec_id:
            initial['fittingspec'] = get_object_or_404(
                FittingSpec.objects.visible_to_user(self.request.user),
                pk=fittingspec_id)

        if dataset_id:
            initial['dataset'] = get_object_or_404(
                Dataset.objects.visible_to_user(self.request.user),
                pk=dataset_id)

        return initial

    def form_valid(self, form):
        self.runnable, is_new = submit_fitting(
            form.cleaned_data['model_version'],
            form.cleaned_data['protocol_version'],
            form.cleaned_data['fittingspec_version'],
            form.cleaned_data['dataset'],
            self.request.user,
            True,
        )

        queued = self.runnable.status == FittingResultVersion.STATUS_QUEUED

        if is_new:
            if queued:
                messages.info(self.request, "Fitting experiment submitted to the queue.")
            else:
                messages.error(self.request, "Fitting experiment could not be run: " + self.runnable.return_text)
        else:
            messages.info(self.request, "Fitting experiment was already run.")

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('fitting:result:version', args=[self.runnable.fittingresult.pk, self.runnable.pk])


class FittingResultFilterJsonView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    JSON view of valid fitting result input values based on those already selected

    For example, if a model id is specified (as a GET param), only versions of that model
    (which are visible to the user) will be included in the results. Otherwise all visible
    models and versions will be in the results (which are simply a list of database
    IDs of the relevant objects)

    Connections between protocols, fitting specs and datasets are also enforced.
    """
    permission_required = 'fitting.run_fits'

    def get(self, request, *args, **kwargs):
        options = {}

        model_versions = CachedModelVersion.objects.visible_to_user(request.user)
        models = ModelEntity.objects.filter(cachedmodel__versions__in=model_versions)
        protocol_versions = CachedProtocolVersion.objects.visible_to_user(request.user)
        protocols = ProtocolEntity.objects.filter(cachedprotocol__versions__in=protocol_versions)
        fittingspec_versions = CachedFittingSpecVersion.objects.visible_to_user(request.user)
        fittingspecs = FittingSpec.objects.filter(cachedfittingspec__versions__in=fittingspec_versions)
        datasets = Dataset.objects.visible_to_user(request.user)

        def _get_int_param(fieldname, _model):
            try:
                pk = int(request.GET.get(fieldname, ''))
                return _model.objects.get(pk=pk)
            except ValueError:
                pass
            except ObjectDoesNotExist:
                pass

        model = _get_int_param('model', ModelEntity)
        protocol = _get_int_param('protocol', ProtocolEntity)
        fittingspec = _get_int_param('fittingspec', FittingSpec)
        dataset = _get_int_param('dataset', Dataset)

        if not protocol:
            if fittingspec:
                protocol = fittingspec.protocol
                protocols = [protocol]
            elif dataset:
                protocol = dataset.protocol
                protocols = [protocol]

        # Restrict to versions of specified model
        if model:
            model_versions = model_versions.filter(entity__entity=model)

        # Restrict to versions of specified fitting spec
        if fittingspec:
            fittingspec_versions = fittingspec_versions.filter(entity__entity=fittingspec)

        # Restrict to versions of specified protocol
        if protocol:
            protocol_versions = protocol_versions.filter(entity__entity=protocol)

            # If no fitting spec was chosen yet, restrict to those linked to this protocol
            if not fittingspec:
                fittingspecs = fittingspecs.filter(protocol=protocol.id)
                fsids = [fs.pk for fs in fittingspecs.filter(protocol=protocol.id)]
                fittingspec_versions = fittingspec_versions.filter(entity__entity__in=fsids)

            # If no dataset was chosen yet, restrict to those linked to this protocol
            if not dataset:
                datasets = datasets.filter(protocol=protocol.id)

        # These might be either querysets or ID lists
        def _get_ids(qs):
            return [item.id for item in qs]

        options['models'] = _get_ids(models)
        options['model_versions'] = _get_ids(model_versions)
        options['protocols'] = _get_ids(protocols)
        options['protocol_versions'] = _get_ids(protocol_versions)
        options['fittingspecs'] = _get_ids(fittingspecs)
        options['fittingspec_versions'] = _get_ids(fittingspec_versions)
        options['datasets'] = _get_ids(datasets)

        return JsonResponse({
            'fittingResultOptions': options
        })


class FittingResultRerunView(PermissionRequiredMixin, View):
    permission_required = 'fitting.run_fits'

    def handle_no_permission(self):
        return JsonResponse({
            'newExperiment': {
                'response': False,
                'responseText': 'You are not allowed to run fitting experiments',
            }
        })

    def post(self, request, *args, **kwargs):
        if 'rerun' in request.POST:
            version = get_object_or_404(FittingResultVersion, pk=request.POST['rerun'])

            version, is_new = submit_fitting(
                version.fittingresult.model_version,
                version.fittingresult.protocol_version,
                version.fittingresult.fittingspec_version,
                version.fittingresult.dataset,
                request.user,
                rerun_ok=True
            )

            queued = version.status == FittingResultVersion.STATUS_QUEUED
            version_url = reverse('fitting:result:version', args=[version.fittingresult.id, version.id])
            if queued:
                msg = " submitted to the queue."
            else:
                msg = " could not be run: " + version.return_text

            return JsonResponse({
                'newExperiment': {
                    'expId': version.fittingresult.id,
                    'versionId': version.id,
                    'url': version_url,
                    'expName': version.fittingresult.name,
                    'status': version.status,
                    'response': (not is_new) or queued,
                    'responseText': "<a href='{}'>Experiment {}</a> {}".format(
                        version_url, version.fittingresult.name, msg
                    )
                }
            })
        else:
            return JsonResponse({
                'newExperiment': {
                    'response': False,
                    'responseText': 'You must specify a fitting experiment to rerun',
                }
            })
