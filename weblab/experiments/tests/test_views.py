import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core import recipes
from experiments.models import ExperimentVersion


@pytest.fixture(autouse=True)
def fake_experiment_path(settings, tmpdir):
    settings.EXPERIMENT_BASE = str(tmpdir)
    return settings.EXPERIMENT_BASE


def mock_submit(url, body):
    return Mock(content=('%s succ celery-task-id' % body['signature']).encode())


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


@patch('requests.post', side_effect=mock_submit)
@pytest.mark.django_db
class TestNewExperimentView:
    @pytest.mark.usefixtures('logged_in_user')
    def test_submits_experiment(self, mock_post,
                                client, model_with_version, protocol_with_version):

        model = model_with_version
        protocol = protocol_with_version
        model_version = model.repo.latest_commit.hexsha
        protocol_version = protocol.repo.latest_commit.hexsha
        response = client.post(
            '/experiments/new',
            {
                'model': model.pk,
                'protocol': protocol.pk,
                'model_version': model_version,
                'protocol_version': protocol_version,
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


@pytest.yield_fixture
def omex_file():
    omex_path = str(Path(__file__).absolute().parent.joinpath('./test.omex'))
    with open(omex_path, 'rb') as fp:
        yield fp


@pytest.mark.django_db
class TestExperimentCallbackView:

    def test_saves_valid_experiment_results(self, client, queued_experiment, omex_file):
        response = client.post('/experiments/callback', {
            'signature': queued_experiment.signature,
            'returntype': 'success',
            'experiment': omex_file,
        })

        assert response.status_code == 200

        # this checks that the form was saved
        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'SUCCESS'

    def test_returns_form_errors(self, client):
        response = client.post('/experiments/callback', {
            'signature': 1,
            'returntype': 'success',
        })

        assert response.status_code == 200

        data = json.loads(response.content.decode())
        assert data['error'] == 'invalid signature'
