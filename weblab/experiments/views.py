from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.urlresolvers import reverse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormMixin

from entities.models import ModelEntity, ProtocolEntity

from .forms import ExperimentSimulateCallbackForm
from .models import Experiment, ExperimentVersion
from .processing import process_callback, submit_experiment


class ExperimentsView(LoginRequiredMixin, TemplateView):
    """
    List all user's experiments
    """
    template_name = 'experiments/experiments.html'


class ExperimentMatrixJsonView(View):
    """
    Serve up JSON for experiment matrix
    """
    @staticmethod
    def entity_json(entity):
        return {
            'id': entity.id,
            'entity_id': entity.id,
            'author': str(entity.author.full_name),
            'visibility': entity.visibility,
            'created': entity.creation_date,
            'name': entity.name,
            'url': reverse(
                'entities:%s_version' % entity.entity_type,
                args=[entity.id, 'latest']
            ),
            # TODO: fill these fields in
            'version': '',
            'tags': '',
            'commitMessage': '',
            'numFiles': '',
        }

    def get(self, request, *args, **kwargs):
        q_visibility = request.user.visibility_query
        models = {
            model.pk: self.entity_json(model)
            for model in ModelEntity.objects.filter(q_visibility)
        }

        protocols = {
            protocol.pk: self.entity_json(protocol)
            for protocol in ProtocolEntity.objects.filter(q_visibility)
        }

        experiments = {
            exp.pk: {
                'entity_id': exp.id,
                'latestResult': exp.latest_result,
                'protocol': self.entity_json(exp.protocol),
                'model': self.entity_json(exp.model),
            }
            for exp in Experiment.objects.filter(q_visibility)
        }

        return JsonResponse({
            'getMatrix': {
                'models': models,
                'protocols': protocols,
                'experiments': experiments,
            }
        })


class NewExperimentView(View):
    def post(self, request, *args, **kwargs):
        # Does user have permission to do this?
        #
        model = get_object_or_404(ModelEntity, pk=request.POST['model'])
        protocol = get_object_or_404(ProtocolEntity, pk=request.POST['protocol'])

        version = submit_experiment(model, protocol, request.user)
        success = version.experiment.latest_result == ExperimentVersion.STATUS_QUEUED

        return JsonResponse({
            'newExperiment': {
                'expId': version.experiment.id,
                'versionId': version.id,
                'expName': version.experiment.name,
                'response': success,
                'responseText': (
                    "Experiment submitted. Based on the size of the queue "
                    "it might take some time until we can process your job."
                ) if success else version.return_text
            }
        })


class ExperimentCallbackView(View):
    def post(self, request, *args, **kwargs):
        result = process_callback(request.POST, request.FILES)
        return JsonResponse(result)


class ExperimentVersionView(DetailView):
    model = ExperimentVersion


@method_decorator(staff_member_required, name='dispatch')
class ExperimentSimulateCallbackView(FormMixin, DetailView):
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
        return reverse('experiments:simulate_callback',
                       args=[self.object.experiment.pk, self.object.pk])

    def form_valid(self, form):
        self.request.POST

        data = dict(
            signature=self.kwargs['pk'],
            **form.data
        )

        result = process_callback(data, {'experiment': form.files.get('upload')})

        if 'error' in result:
            messages.error(self.request, result['error'])

        return super().form_valid(form)
