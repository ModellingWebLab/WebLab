import json

import pytest

from core import recipes
from experiments.models import ExperimentVersion


@pytest.mark.django_db
class TestExperimentMatrix:
    @pytest.mark.usefixtures('logged_in_user')
    def test_matrix(self, client):
        model = recipes.model.make()
        protocol = recipes.protocol.make()
        exp = recipes.experiment.make(model=model, protocol=protocol)

        response = client.get('/experiments/matrix')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert str(model.pk) in data['getMatrix']['models']
        assert str(protocol.pk) in data['getMatrix']['protocols']
        assert str(exp.pk) in data['getMatrix']['experiments']


@pytest.mark.django_db
class TestNewExperimentView:
    @pytest.mark.usefixtures('logged_in_user')
    def test_submits_experiment(self, client, model_with_version, protocol_with_version):
        response = client.post(
            '/experiments/new',
            {
                'model': model_with_version.pk,
                'protocol': protocol_with_version.pk,
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())

        assert 'newExperiment' in data

        version = ExperimentVersion.objects.get()

        assert data['newExperiment']['expId'] == version.experiment.id
        assert data['newExperiment']['versionId'] == version.id
        assert data['newExperiment']['expName'] == version.experiment.name
        assert data['newExperiment']['response']
