import json
from unittest.mock import Mock, patch

import pytest

from core import recipes
from experiments.models import ExperimentVersion


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
    def test_submits_experiment(self, mock_post, client, model_with_version, protocol_with_version):
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


@pytest.mark.django_db
class TestExperimentCallbackView:
    @pytest.mark.parametrize('returned_status,stored_status', [
        ('success', 'SUCCESS'),
        ('running', 'RUNNING'),
        ('partial', 'PARTIAL'),
        ('inapplicable', 'INAPPLICABLE'),
        ('failed', 'FAILED'),
        ('something else', 'FAILED'),
    ])
    def test_records_status(self, returned_status, stored_status,
                            client, queued_experiment):
        response = client.post('/experiments/callback', {
            'signature': queued_experiment.signature,
            'returntype': returned_status,
        })

        assert response.status_code == 200

        queued_experiment.refresh_from_db()
        assert queued_experiment.status == stored_status

    @pytest.mark.parametrize('status,message', [
        ('inapplicable', 'list, of, missing, terms'),
        ('failed', 'python stacktrace'),
    ])
    def test_records_errormessage(self, status, message,
                                  client, queued_experiment):
        response = client.post('/experiments/callback', {
            'signature': queued_experiment.signature,
            'returntype': status,
            'returnmsg': message,
        })

        assert response.status_code == 200
        queued_experiment.refresh_from_db()
        assert queued_experiment.return_text == message

    @pytest.mark.parametrize('status,message', [
        ('success', 'finished'),
        ('partial', 'finished'),
        ('failed', 'finished'),
        ('running', 'running'),
    ])
    def test_records_default_errormessage(self, status, message,
                                          client, queued_experiment):
        response = client.post('/experiments/callback', {
            'signature': queued_experiment.signature,
            'returntype': status,
        })

        assert response.status_code == 200
        queued_experiment.refresh_from_db()
        assert queued_experiment.return_text == message

    def test_records_task_id(self, client, queued_experiment):
        response = client.post('/experiments/callback', {
            'signature': queued_experiment.signature,
            'returntype': 'running',
            'taskid': 'task-id-1',
        })

        assert response.status_code == 200
        queued_experiment.refresh_from_db()
        assert queued_experiment.task_id == 'task-id-1'
