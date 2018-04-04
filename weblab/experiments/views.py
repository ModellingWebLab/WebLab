from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.urlresolvers import reverse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import TemplateView

from entities.models import ModelEntity, ProtocolEntity

from .models import Experiment
from .processing import submit_experiment


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

        return JsonResponse({
            'newExperiment': {
                'expId': version.experiment.id,
                'versionId': version.id,
                'expName': version.experiment.name,
                'response': True,
                'responseText': (
                    "Experiment submitted. Based on the size of the queue "
                    "it might take some time until we can process your job."
                )
            }
        })
