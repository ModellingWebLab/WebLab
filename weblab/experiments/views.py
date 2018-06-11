import logging
import mimetypes
import os.path
import urllib.parse

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.text import get_valid_filename
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import FormMixin

from core.visibility import VisibilityMixin, visibility_query
from entities.models import ModelEntity, ProtocolEntity

from .forms import ExperimentSimulateCallbackForm
from .models import Experiment, ExperimentVersion
from .processing import process_callback, submit_experiment


logger = logging.getLogger(__name__)


class ExperimentsView(TemplateView):
    """
    Show the default experiment matrix view for this user (or the public)
    """
    template_name = 'experiments/experiments.html'


class ExperimentMatrixJsonView(View):
    """
    Serve up JSON for experiment matrix
    """
    @classmethod
    def entity_json(cls, entity):
        commit = entity.repo.latest_commit
        version = commit.hexsha if commit else ''
        return {
            'id': entity.id,
            'entity_id': entity.id,
            'author': str(entity.author.full_name),
            'visibility': entity.visibility,
            'created': entity.created_at,
            'name': entity.name,
            'url': reverse(
                'entities:%s_version' % entity.entity_type,
                args=[entity.id, version or 'latest']
            ),
            'version': version
        }

    @classmethod
    def experiment_json(cls, experiment):
        try:
            version = experiment.latest_version
        except ExperimentVersion.DoesNotExist:
            version = None

        return {
            'entity_id': experiment.id,
            'latestResult': experiment.latest_result,
            'protocol': cls.entity_json(experiment.protocol),
            'model': cls.entity_json(experiment.model),
            'url': reverse(
                'experiments:version',
                args=[experiment.id, version.id]
            ) if version else '',
        }

    def get(self, request, *args, **kwargs):
        q_visibility = visibility_query(request.user)
        q_models = ModelEntity.objects.filter(q_visibility)
        q_protocols = ProtocolEntity.objects.filter(q_visibility)

        models = {
            model.pk: self.entity_json(model)
            for model in q_models
        }

        protocols = {
            protocol.pk: self.entity_json(protocol)
            for protocol in q_protocols
        }

        # Only give info on experiments involving the correct entity versions
        experiments = {}
        for exp in Experiment.objects.filter(model__in=q_models, protocol__in=q_protocols):
            if (exp.model_version == models[exp.model.pk]['version'] and
                    exp.protocol_version == protocols[exp.protocol.pk]['version']):
                experiments[exp.pk] = self.experiment_json(exp)

        return JsonResponse({
            'getMatrix': {
                'models': models,
                'protocols': protocols,
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

        version = submit_experiment(model, model_version, protocol, protocol_version, request.user)
        success = version.status == ExperimentVersion.STATUS_QUEUED

        return JsonResponse({
            'newExperiment': {
                'expId': version.experiment.id,
                'versionId': version.id,
                'url': reverse(
                    'experiments:version',
                    args=[version.experiment.id, version.id],
                ),
                'expName': version.experiment.name,
                'response': success,
                'responseText': (
                    "Experiment submitted to the queue."
                ) if success else version.return_text
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


class ExperimentComparisonView(TemplateView):
    """
    Compare multiple experiment versions
    """
    template_name = 'experiments/experimentversion_compare.html'

    def get_context_data(self, **kwargs):
        pks = {int(pk) for pk in self.kwargs['version_pks'][1:].split('/')}
        versions = ExperimentVersion.objects.visible_to(
            self.request.user).filter(pk__in=pks).order_by('created_at')

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

    def _version_json(self, version):
        """
        JSON for a single experiment version

        :param version: ExperimentVersion object
        """
        files = [
            self._file_json(version, f)
            for f in version.files
            if f.name not in ['manifest.xml', 'metadata.rdf']
        ]
        return {
            'id': version.id,
            'author': version.author.full_name,
            'status': version.status,
            'parsedOk': False,
            'visibility': version.visibility,
            'created': version.created_at,
            'name': version.experiment.name,
            'experimentId': version.experiment.id,
            'versionId': version.id,
            'files': files,
            'numFiles': len(files),
            'url': reverse(
                'experiments:version', args=[version.experiment.id, version.id]
            ),
            'download_url': reverse(
                'experiments:archive', args=[version.experiment.id, version.id]
            ),
            'modelName': version.experiment.model.name,
            'protoName': version.experiment.protocol.name,
        }

    def get(self, request, *args, **kwargs):
        pks = {int(pk) for pk in self.kwargs['version_pks'][1:].split('/')}
        versions = ExperimentVersion.objects.visible_to(
            self.request.user).filter(pk__in=pks).order_by('created_at')

        response = {
            'getEntityInfos': {
                'entities': [
                    self._version_json(version) for version in versions
                ]
            }
        }

        if len(versions) <= len(pks):
            response['notifications'] = {
                'errors': [
                    'Some requested experiment results could not be found '
                    '(or you don\'t have permission to see them)'
                ]
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
