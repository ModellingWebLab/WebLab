import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse
from django.db.models import F, Q
from django.db.models.functions import Coalesce
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.text import get_valid_filename
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, TemplateView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import FormMixin
from guardian.shortcuts import get_objects_for_user

from core.visibility import VisibilityMixin
from datasets import views as dataset_views
from entities.models import ModelEntity, ProtocolEntity
from repocache.models import CACHED_VERSION_TYPE_MAP

from .forms import ExperimentSimulateCallbackForm
from .models import (
    Experiment,
    ExperimentVersion,
    PlannedExperiment,
    RunningExperiment,
)
from .processing import process_callback, submit_experiment


logger = logging.getLogger(__name__)


class ExperimentsView(TemplateView):
    """
    Show the default experiment matrix view for this user (or the public)
    """
    template_name = 'experiments/experiments.html'


class ExperimentTasks(LoginRequiredMixin, ListView):
    """
    Show running versions of all experiments
    Delete checked versions
    """
    model = RunningExperiment
    template_name = "experiments/experiment_tasks.html"

    def get_queryset(self):
        return RunningExperiment.objects.filter(
            runnable__author=self.request.user
        ).order_by(
            'runnable__created_at',
        ).select_related('runnable',
                         'runnable__experimentversion__experiment')

    def post(self, request):
        for running_exp_id in request.POST.getlist('chkBoxes[]'):
            exp_version = ExperimentVersion.objects.get(id=running_exp_id)
            if not exp_version.author == self.request.user:
                raise Http404
            exp_version.delete()
        return redirect(reverse('experiments:tasks'))


class ExperimentMatrixJsonView(View):
    """
    Serve up JSON for experiment matrix
    """
    @classmethod
    def entity_json(cls, entity, version, *, extend_name, visibility, author, friendly_version=''):
        if extend_name:
            name = '%s @ %s' % (entity.name, friendly_version or version)
        else:
            name = entity.name

        _json = {
            'id': version,
            'entityId': entity.id,
            'author': author,
            'visibility': visibility,
            'created': entity.created_at,
            'name': name,
            'url': reverse(
                'entities:version',
                args=[entity.entity_type, entity.id, version]
            ),
        }

        return _json

    @classmethod
    def experiment_version_json(cls, version):
        return {
            'id': version.id,
            'entity_id': version.experiment.id,
            'latestResult': version.status,
            'protocol': cls.entity_json(
                version.experiment.protocol, version.experiment.protocol_version.sha,
                extend_name=True, visibility=version.protocol_visibility, author=version.protocol_author,
            ),
            'model': cls.entity_json(
                version.experiment.model, version.experiment.model_version.sha,
                extend_name=True, visibility=version.model_visibility, author=version.model_author,
            ),
            'url': reverse(
                'experiments:version',
                args=[version.experiment.id, version.id]
            ),
        }

    def versions_query(self, entity_type, requested_versions, entity_query, visibility_where):
        """Get the query expression for selecting entity versions to display."""
        CachedEntityVersion = CACHED_VERSION_TYPE_MAP[entity_type]
        if requested_versions:
            if requested_versions[0] == '*':
                q_entity_versions = CachedEntityVersion.objects.filter(
                    entity__entity__in=entity_query,
                )
            else:
                q_entity_versions = CachedEntityVersion.objects.filter(
                    entity__entity__in=entity_query,
                    sha__in=requested_versions,
                )
        else:
            where = visibility_where & Q(entity__entity__in=entity_query)
            q_entity_versions = CachedEntityVersion.objects.filter(
                where,
            ).order_by(
                'entity__id',
                '-timestamp',
                '-pk',
            ).distinct(
                'entity__id',
            )
        q_entity_versions = q_entity_versions.select_related(
            'entity',
            'entity__entity',
        ).annotate(
            author_name=F('entity__entity__author__full_name'),
            friendly_name=Coalesce(F('tags__tag'), F('sha')),
        )
        return q_entity_versions

    def get(self, request, *args, **kwargs):
        # Extract and sanity-check call arguments
        user = request.user
        model_pks = list(map(int, request.GET.getlist('modelIds[]')))
        protocol_pks = list(map(int, request.GET.getlist('protoIds[]')))
        model_versions = request.GET.getlist('modelVersions[]')
        protocol_versions = request.GET.getlist('protoVersions[]')
        subset = request.GET.get('subset', 'all' if model_pks or protocol_pks else 'moderated')
        show_fits = 'show_fits' in request.GET

        if model_versions and len(model_pks) > 1:
            return JsonResponse({
                'notifications': {
                    'errors': ['Only one model ID can be used when versions are specified'],
                }
            })

        if protocol_versions and len(protocol_pks) > 1:
            return JsonResponse({
                'notifications': {
                    'errors': ['Only one protocol ID can be used when versions are specified'],
                }
            })

        # Base models/protocols to show
        q_models = ModelEntity.objects.all()
        if model_pks:
            q_models = q_models.filter(id__in=set(model_pks))
        q_protocols = ProtocolEntity.objects.all()
        if protocol_pks:
            q_protocols = q_protocols.filter(id__in=set(protocol_pks))

        # Base visibility: don't show private versions, unless only showing moderated versions
        if subset == 'moderated':
            visibility_where = Q(visibility='moderated')
        else:
            visibility_where = ~Q(visibility='private')

        if user.is_authenticated:
            q_mine = Q(author=user)
            # Can also include versions the user has explicit permission to see
            visible_entities = user.entity_set.union(
                get_objects_for_user(user, 'entities.edit_entity', with_superuser=False)
            ).values_list(
                'id', flat=True
            )
        else:
            q_mine = Q()
            visible_entities = set()

        # Figure out which entity versions will be listed on the axes
        # We look at which subset has been requested: moderated, mine, all (visible), public
        q_moderated_models = Q(cachedmodel__versions__visibility='moderated')
        q_moderated_protocols = Q(cachedprotocol__versions__visibility='moderated')
        q_public_models = Q(cachedmodel__versions__visibility__in=['public', 'moderated'])
        q_public_protocols = Q(cachedprotocol__versions__visibility__in=['public', 'moderated'])
        if subset == 'moderated':
            q_models = q_models.filter(q_moderated_models)
            q_protocols = q_protocols.filter(q_moderated_protocols)
        elif subset == 'mine' and user.is_authenticated:
            if request.GET.get('moderated-models', 'true') == 'true':
                q_models = q_models.filter(q_mine | q_moderated_models)
            else:
                q_models = q_models.filter(q_mine).filter(
                    cachedmodel__versions__visibility__in=['public', 'private'])
            if request.GET.get('moderated-protocols', 'true') == 'true':
                q_protocols = q_protocols.filter(q_mine | q_moderated_protocols)
            else:
                q_protocols = q_protocols.filter(q_mine).filter(
                    cachedprotocol__versions__visibility__in=['public', 'private'])
        elif subset == 'public':
            q_models = q_models.filter(q_public_models)
            q_protocols = q_protocols.filter(q_public_protocols)
        elif subset == 'all':
            shared_models = ModelEntity.objects.shared_with_user(user)
            if model_pks:
                shared_models = shared_models.filter(id__in=set(model_pks))
            q_models = q_models.filter(q_public_models | q_mine).union(shared_models)
            shared_protocols = ProtocolEntity.objects.shared_with_user(user)
            if protocol_pks:
                shared_protocols = shared_protocols.filter(id__in=set(protocol_pks))
            q_protocols = q_protocols.filter(q_public_protocols | q_mine).union(shared_protocols)
        else:
            q_models = ModelEntity.objects.none()
            q_protocols = ProtocolEntity.objects.none()

        if subset not in ['moderated', 'public']:
            visibility_where = visibility_where | Q(entity__entity__in=visible_entities)

        # If specific versions have been requested, show at most those
        q_model_versions = self.versions_query('model', model_versions, q_models.values('pk'), visibility_where)
        if show_fits:  # Temporary hack
            protocol_visibility_where = visibility_where & Q(entity__entity__is_fitting_spec=True)
        else:
            protocol_visibility_where = visibility_where & Q(entity__entity__is_fitting_spec=False)
        q_protocol_versions = self.versions_query('protocol', protocol_versions, q_protocols.values('pk'),
                                                  protocol_visibility_where)

        # Get the JSON data needed to display the matrix axes
        model_versions = [self.entity_json(version.entity.entity, version.sha,
                                           extend_name=bool(model_versions),
                                           visibility=version.visibility,
                                           author=version.author_name,
                                           friendly_version=version.friendly_name)
                          for version in q_model_versions]
        model_versions = {ver['id']: ver for ver in model_versions}

        protocol_versions = [self.entity_json(version.entity.entity, version.sha,
                                              extend_name=bool(protocol_versions),
                                              visibility=version.visibility,
                                              author=version.author_name,
                                              friendly_version=version.friendly_name)
                             for version in q_protocol_versions]
        protocol_versions = {ver['id']: ver for ver in protocol_versions}

        # Only give info on experiments involving the correct entity versions
        experiments = {}
        q_experiments = Experiment.objects.filter(
            model__in=q_models,
            model_version__in=q_model_versions,
            protocol__in=q_protocols,
            protocol_version__in=q_protocol_versions,
        )
        q_experiment_versions = ExperimentVersion.objects.filter(
            experiment__in=q_experiments,
        ).order_by(
            'experiment__id',
            '-created_at',
        ).distinct(
            'experiment__id'
        ).select_related(
            'experiment',
            'experiment__protocol', 'experiment__model',
            'experiment__protocol__cachedprotocol', 'experiment__model__cachedmodel',
        ).annotate(
            protocol_visibility=F('experiment__protocol_version__visibility'),
            model_visibility=F('experiment__model_version__visibility'),
            protocol_author=F('experiment__protocol__author__full_name'),
            model_author=F('experiment__model__author__full_name'),
        )
        for exp_ver in q_experiment_versions:
            experiments[exp_ver.experiment.pk] = self.experiment_version_json(exp_ver)

        return JsonResponse({
            'getMatrix': {
                'models': model_versions,
                'protocols': protocol_versions,
                'experiments': experiments,
            }
        })


class NewExperimentView(PermissionRequiredMixin, View):
    permission_required = 'experiments.create_experiment'

    def handle_no_permission(self):
        return JsonResponse({
            'newExperiment': {
                'response': False,
                'responseText': 'You are not allowed to create a new experiment',
            }
        })

    def post(self, request, *args, **kwargs):
        if 'rerun' in request.POST:
            exp_ver = get_object_or_404(ExperimentVersion, pk=request.POST['rerun'])
            exp = exp_ver.experiment
            model = exp.model
            protocol = exp.protocol
            model_sha = exp.model_version.sha
            protocol_sha = exp.protocol_version.sha
        else:
            model = get_object_or_404(ModelEntity, pk=request.POST['model'])
            protocol = get_object_or_404(ProtocolEntity, pk=request.POST['protocol'])
            model_sha = request.POST['model_version']
            protocol_sha = request.POST['protocol_version']

        model_version = model.repocache.get_version(model_sha)
        protocol_version = protocol.repocache.get_version(protocol_sha)
        version, is_new = submit_experiment(model_version, protocol_version,
                                            request.user, 'rerun' in request.POST or 'planned' in request.POST)
        queued = version.status == ExperimentVersion.STATUS_QUEUED
        if is_new and version.status != ExperimentVersion.STATUS_FAILED:
            # Remove from planned experiments
            PlannedExperiment.objects.filter(
                model=model, model_version=model_sha,
                protocol=protocol, protocol_version=protocol_sha
            ).delete()

        version_url = reverse('experiments:version',
                              args=[version.experiment.id, version.id])
        if is_new:
            if queued:
                msg = " submitted to the queue."
            else:
                msg = " could not be run: " + version.return_text
        else:
            msg = " was already run."
        return JsonResponse({
            'newExperiment': {
                'expId': version.experiment.id,
                'versionId': version.id,
                'url': version_url,
                'expName': version.experiment.name,
                'status': version.status,
                'response': (not is_new) or queued,
                'responseText': "<a href='{}'>Experiment {}</a> {}".format(
                    version_url, version.experiment.name, msg
                )
            }
        })


@method_decorator(csrf_exempt, name='dispatch')
class ExperimentCallbackView(View):
    def post(self, request, *args, **kwargs):
        result = process_callback(request.POST, request.FILES)
        return JsonResponse(result)


class ExperimentVersionView(VisibilityMixin, DetailView):
    model = ExperimentVersion
    context_object_name = 'version'


class ExperimentVersionListView(VisibilityMixin, DetailView):
    """Show all versions of an experiment"""
    model = Experiment
    context_object_name = 'experiment'
    template_name = 'experiments/experiment_versions.html'


class ExperimentDeleteView(dataset_views.DatasetDeleteView):
    """
    Delete all versions of an experiment
    """
    model = Experiment


class ExperimentVersionDeleteView(dataset_views.DatasetDeleteView):
    """
    Delete a single version of an experiment
    """
    model = ExperimentVersion

    def get_success_url(self, *args, **kwargs):
        return reverse('experiments:versions', args=[self.get_object().experiment.id])


class ExperimentComparisonView(TemplateView):
    """
    Compare multiple experiment versions
    """
    template_name = 'experiments/experimentversion_compare.html'

    def get_context_data(self, **kwargs):
        pks = set(map(int, self.kwargs['version_pks'].strip('/').split('/')))
        versions = ExperimentVersion.objects.filter(pk__in=pks).order_by('created_at')
        versions = [v for v in versions if v.experiment.is_visible_to_user(self.request.user)]

        if len(versions) < len(pks):
            messages.error(
                self.request,
                'Some requested experiment results could not be found '
                '(or you don\'t have permission to see them)'
            )

        kwargs.update({
            'experiment_versions': versions,
        })
        return super().get_context_data(**kwargs)


class ExperimentComparisonJsonView(View):
    """
    Serve up JSON view of multiple experiment versions for comparison
    """
    def _version_json(self, version, model_version_in_name, protocol_version_in_name):
        """
        JSON for a single experiment version

        :param version: ExperimentVersion object
        :param model_version_in_name: Whether to include model version specifier in name field
        :param protocol_version_in_name: Whether to include protocol version specifier in name field
        """
        exp = version.experiment
        ns = self.request.resolver_match.namespace
        url_args = [exp.id, version.id]
        details = version.get_json(ns, url_args)
        details.update({
            'name': exp.get_name(model_version_in_name, protocol_version_in_name),
            'url': reverse(ns + ':version', args=url_args),
            'versionId': version.id,
            'modelName': exp.model.name,
            'protoName': exp.protocol.name,
            'modelVersion': exp.model_version.get_name(),
            'protoVersion': exp.protocol_version.get_name(),
            'runNumber': version.run_number,
        })
        return details

    def get(self, request, *args, **kwargs):
        pks = {int(pk) for pk in self.kwargs['version_pks'][1:].split('/') if pk}
        versions = ExperimentVersion.objects.filter(pk__in=pks).order_by('created_at')
        versions = [v for v in versions if v.experiment.is_visible_to_user(self.request.user)]

        models = set((v.experiment.model, v.experiment.model_version) for v in versions)
        protocols = set((v.experiment.protocol, v.experiment.protocol_version) for v in versions)
        compare_model_versions = len(models) > len(dict(models))
        compare_protocol_versions = len(protocols) > len(dict(protocols))

        response = {
            'getEntityInfos': {
                'entities': [
                    self._version_json(version, compare_model_versions, compare_protocol_versions)
                    for version in versions
                ]
            }
        }

        return JsonResponse(response)


@method_decorator(staff_member_required, name='dispatch')
class ExperimentSimulateCallbackView(FormMixin, DetailView):
    """
    Allow a staff member to simulate the experiment result callback.

    This is mainly for debug purposes.
    """
    model = ExperimentVersion
    form_class = ExperimentSimulateCallbackForm
    template_name = 'experiments/simulate_callback_form.html'
    context_object_name = 'version'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse('experiments:version',
                       args=[self.object.experiment.pk, self.object.pk])

    def form_valid(self, form):
        data = dict(
            signature=self.get_object().signature,
            **form.cleaned_data
        )

        result = process_callback(data, {'experiment': form.files.get('upload')})

        if 'error' in result:
            messages.error(self.request, result['error'])
            logger.error(result['error'])

        else:
            messages.info(self.request, 'Experiment status updated')

        return super().form_valid(form)


class ExperimentVersionJsonView(VisibilityMixin, SingleObjectMixin, View):
    """
    Serve up json view of an experiment verson
    """
    model = ExperimentVersion

    def get(self, request, *args, **kwargs):
        version = self.get_object()
        ns = self.request.resolver_match.namespace
        url_args = [version.experiment.id, version.id]
        details = version.get_json(ns, url_args)
        details.update({
            'status': version.status,
            'version': version.id,
            'experimentId': version.experiment.id,
        })
        return JsonResponse({
            'version': details,
        })


class ExperimentFileDownloadView(dataset_views.DatasetFileDownloadView):
    """
    Download an individual file from an experiment
    """
    model = ExperimentVersion


class ExperimentVersionArchiveView(dataset_views.DatasetArchiveView):
    """
    Download a combine archive of an experiment version
    """
    model = ExperimentVersion

    def get_archive_name(self, version):
        """For historical reasons this is different from the archive_name."""
        return get_valid_filename('%s.zip' % version.experiment.name)
