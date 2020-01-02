import logging
import mimetypes
import os.path
import urllib.parse

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.core.urlresolvers import reverse
from django.db.models import (
    F,
    OuterRef,
    Q,
    Subquery,
)
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.text import get_valid_filename
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, TemplateView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import DeleteView, FormMixin
from guardian.shortcuts import get_objects_for_user

from core.visibility import VisibilityMixin, visible_entity_ids
from entities.models import ModelEntity, ProtocolEntity
from repocache.entities import get_moderated_entity_ids, get_public_entity_ids
from repocache.models import CachedEntityVersion

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
            experiment_version__author=self.request.user
        ).order_by(
            'experiment_version__created_at',
        ).select_related('experiment_version', 'experiment_version__experiment')

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
                version.experiment.protocol, version.experiment.protocol_version,
                extend_name=True, visibility=version.protocol_visibility, author=version.protocol_author,
            ),
            'model': cls.entity_json(
                version.experiment.model, version.experiment.model_version,
                extend_name=True, visibility=version.model_visibility, author=version.model_author,
            ),
            'url': reverse(
                'experiments:version',
                args=[version.experiment.id, version.id]
            ),
        }

    def versions_query(self, entity_type, requested_versions, entity_query, visibility_where):
        """Get the query expression for selecting entity versions to display."""
        if requested_versions:
            if requested_versions[0] == '*':
                q_entity_versions = CachedEntityVersion.objects.filter(
                    entity__entity__entity_type=entity_type,
                    entity__entity__in=entity_query,
                )
            else:
                q_entity_versions = CachedEntityVersion.objects.filter(
                    entity__entity__entity_type=entity_type,
                    entity__entity__in=entity_query,
                    sha__in=requested_versions,
                )
        else:
            where = visibility_where & Q(entity__entity__entity_type=entity_type) & Q(entity__entity__in=entity_query)
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

        # Base visibility: don't show private versions...
        visibility_where = ~Q(visibility='private')

        if user.is_authenticated:
            # Can also include versions the user has explicit permission to see
            visible_entities = user.entity_set.union(
                get_objects_for_user(user, 'entities.edit_entity', with_superuser=False)
            ).values_list(
                'id', flat=True
            )
        else:
            visible_entities = set()

        # Figure out which entity versions will be listed on the axes
        # If specific versions have been requested, show at most those
        # (filtering out any this user can't see)
        # Otherwise we look at which subset has been requested: moderated, mine, all (visible), public
        if not model_pks or not protocol_pks:
            if subset == 'moderated':
                entity_ids = get_moderated_entity_ids()
                visibility_where = Q(visibility='moderated')
            elif subset == 'mine' and user.is_authenticated:
                # TODO? This is still 3 queries...
                entity_ids = set(user.entity_set.values_list('id', flat=True))

                moderated_model_ids = get_moderated_entity_ids('model')
                if request.GET.get('moderated-models', 'true') == 'true':
                    entity_ids |= moderated_model_ids
                else:
                    entity_ids -= moderated_model_ids

                moderated_protocol_ids = get_moderated_entity_ids('protocol')
                if request.GET.get('moderated-protocols', 'true') == 'true':
                    entity_ids |= moderated_protocol_ids
                else:
                    entity_ids -= moderated_protocol_ids

            elif subset == 'public':
                entity_ids = get_public_entity_ids()
            elif subset == 'all':
                entity_ids = visible_entity_ids(request.user)
            else:
                entity_ids = set()

        if subset not in ['moderated', 'public']:
            visibility_where = visibility_where | Q(entity__entity__in=visible_entities)

        if model_pks:
            model_visibility_where = ~Q(visibility='private') | Q(entity__entity__in=visible_entities)
            model_ids = set(model_pks)
        else:
            model_visibility_where = visibility_where
            model_ids = entity_ids

        q_models = ModelEntity.objects.filter(id__in=model_ids)
        q_model_versions = self.versions_query('model', model_versions, q_models, model_visibility_where)

        if protocol_pks:
            protocol_visibility_where = ~Q(visibility='private') | Q(entity__entity__in=visible_entities)
            protocol_ids = set(protocol_pks)
        else:
            if show_fits:
                protocol_visibility_where = visibility_where & Q(entity__entity__is_fitting_spec=True)
            else:
                protocol_visibility_where = visibility_where & Q(entity__entity__is_fitting_spec=False)
            protocol_ids = entity_ids

        q_protocols = ProtocolEntity.objects.filter(id__in=protocol_ids)
        q_protocol_versions = self.versions_query('protocol', protocol_versions, q_protocols, protocol_visibility_where)

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
            model_version__in=model_versions.keys(),
            protocol__in=q_protocols,
            protocol_version__in=protocol_versions.keys(),
        )
        q_cached_protocol = CachedEntityVersion.objects.filter(
            entity__entity=OuterRef('experiment__protocol'),
            sha=OuterRef('experiment__protocol_version'),
        )
        q_cached_model = CachedEntityVersion.objects.filter(
            entity__entity=OuterRef('experiment__model'),
            sha=OuterRef('experiment__model_version'),
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
            'experiment__protocol__cachedentity', 'experiment__model__cachedentity',
        ).annotate(
            protocol_visibility=Subquery(q_cached_protocol.values('visibility')[:1]),
            model_visibility=Subquery(q_cached_model.values('visibility')[:1]),
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
            model_version = exp.model_version
            protocol_version = exp.protocol_version
        else:
            model = get_object_or_404(ModelEntity, pk=request.POST['model'])
            protocol = get_object_or_404(ProtocolEntity, pk=request.POST['protocol'])
            model_version = request.POST['model_version']
            protocol_version = request.POST['protocol_version']

        version, is_new = submit_experiment(model, model_version, protocol, protocol_version,
                                            request.user, 'rerun' in request.POST or 'planned' in request.POST)
        queued = version.status == ExperimentVersion.STATUS_QUEUED
        if is_new and version.status != ExperimentVersion.STATUS_FAILED:
            # Remove from planned experiments
            PlannedExperiment.objects.filter(
                model=model, model_version=model_version,
                protocol=protocol, protocol_version=protocol_version
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


class ExperimentDeleteView(UserPassesTestMixin, DeleteView):
    """
    Delete all versions of an experiment
    """
    model = Experiment
    # Raise a 403 error rather than redirecting to login,
    # if the user doesn't have delete permissions.
    raise_exception = True

    def test_func(self):
        return self.get_object().is_deletable_by(self.request.user)

    def get_success_url(self, *args, **kwargs):
        return reverse('experiments:list')


class ExperimentVersionDeleteView(UserPassesTestMixin, DeleteView):
    """
    Delete a single version of an experiment
    """
    model = ExperimentVersion
    # Raise a 403 error rather than redirecting to login,
    # if the user doesn't have delete permissions.
    raise_exception = True

    def test_func(self):
        return self.get_object().is_deletable_by(self.request.user)

    def get_success_url(self, *args, **kwargs):
        return reverse('experiments:versions', args=[self.get_object().experiment.id])


class ExperimentComparisonView(TemplateView):
    """
    Compare multiple experiment versions
    """
    template_name = 'experiments/experimentversion_compare.html'

    def get_context_data(self, **kwargs):
        pks = set(map(int, self.kwargs['version_pks'].strip('/').split('/')))
        versions = ExperimentVersion.objects.visible_to(
            self.request.user).filter(pk__in=pks).order_by('created_at')

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
    def _file_json(self, version, archive_file):
        """
        JSON for a single file in the experiment archive

        :param version: ExperimentVersion object
        :param archive_file: ArchiveFile object
        """
        return {
            'id': archive_file.name,
            'author': version.author.full_name,
            'created': version.created_at,
            'name': archive_file.name,
            'filetype': archive_file.fmt,
            'masterFile': archive_file.is_master,
            'size': archive_file.size,
            'url': reverse(
                'experiments:file_download',
                args=[version.experiment.id, version.id, urllib.parse.quote(archive_file.name)]
            )
        }

    def _version_json(self, version, model_version_in_name, protocol_version_in_name):
        """
        JSON for a single experiment version

        :param version: ExperimentVersion object
        :param model_version_in_name: Whether to include model version specifier in name field
        :param protocol_version_in_name: Whether to include protocol version specifier in name field
        """
        files = [
            self._file_json(version, f)
            for f in version.files
            if f.name not in ['manifest.xml', 'metadata.rdf']
        ]
        exp = version.experiment
        return {
            'id': version.id,
            'author': version.author.full_name,
            'status': version.status,
            'parsedOk': False,
            'visibility': version.visibility,
            'created': version.created_at,
            'name': version.experiment.get_name(model_version_in_name, protocol_version_in_name),
            'experimentId': version.experiment.id,
            'versionId': version.id,
            'files': files,
            'numFiles': len(files),
            'url': reverse(
                'experiments:version', args=[exp.id, version.id]
            ),
            'download_url': reverse(
                'experiments:archive', args=[exp.id, version.id]
            ),
            'modelName': exp.model.name,
            'protoName': exp.protocol.name,
            'modelVersion': exp.model.repo.get_name_for_commit(exp.model_version),
            'protoVersion': exp.protocol.repo.get_name_for_commit(exp.protocol_version),
            'runNumber': version.run_number,
        }

    def get(self, request, *args, **kwargs):
        pks = {int(pk) for pk in self.kwargs['version_pks'][1:].split('/') if pk}
        versions = ExperimentVersion.objects.visible_to(
            self.request.user).filter(pk__in=pks).order_by('created_at')

        models = set(versions.values_list('experiment__model', 'experiment__model_version'))
        protocols = set(versions.values_list(
            'experiment__protocol', 'experiment__protocol_version'))
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

    def _file_json(self, archive_file):
        version = self.get_object()
        return {
            'id': archive_file.name,
            'author': version.author.full_name,
            'created': version.created_at,
            'name': archive_file.name,
            'filetype': archive_file.fmt,
            'masterFile': archive_file.is_master,
            'size': archive_file.size,
            'url': reverse(
                'experiments:file_download',
                args=[version.experiment.id, version.id, urllib.parse.quote(archive_file.name)]
            )
        }

    def get(self, request, *args, **kwargs):
        version = self.get_object()
        files = [
            self._file_json(f)
            for f in version.files
            if f.name not in ['manifest.xml', 'metadata.rdf']
        ]

        return JsonResponse({
            'version': {
                'id': version.id,
                'author': version.author.full_name,
                'status': version.status,
                'parsedOk': False,
                'visibility': version.visibility,
                'created': version.created_at,
                'name': version.name,
                'experimentId': version.experiment.id,
                'version': version.id,
                'files': files,
                'numFiles': len(files),
                'download_url': reverse(
                    'experiments:archive', args=[version.experiment.id, version.id]
                ),
            }
        })


class ExperimentFileDownloadView(VisibilityMixin, SingleObjectMixin, View):
    """
    Download an individual file from an experiment
    """
    model = ExperimentVersion

    def get(self, request, *args, **kwargs):
        filename = self.kwargs['filename']
        version = self.get_object()

        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = 'application/octet-stream'

        with version.open_file(filename) as file_:
            response = HttpResponse(content_type=content_type)
            response['Content-Disposition'] = 'attachment; filename=%s' % filename
            response.write(file_.read())

        return response


class ExperimentVersionArchiveView(VisibilityMixin, SingleObjectMixin, View):
    """
    Download a combine archive of an experiment version
    """
    model = ExperimentVersion

    def get(self, request, *args, **kwargs):
        version = self.get_object()
        path = version.archive_path

        if not path.exists():
            raise Http404

        zipfile_name = os.path.join(
            get_valid_filename('%s.zip' % version.experiment.name)
        )

        with path.open('rb') as archive:
            response = HttpResponse(content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename=%s' % zipfile_name
            response.write(archive.read())

        return response
