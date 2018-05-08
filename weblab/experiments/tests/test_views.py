import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from core import recipes
from experiments.models import Experiment, ExperimentVersion


@pytest.fixture(autouse=True)
def fake_experiment_path(settings, tmpdir):
    settings.EXPERIMENT_BASE = str(tmpdir)
    return settings.EXPERIMENT_BASE


@pytest.fixture(autouse=True)
def fake_repo_path(settings, tmpdir):
    settings.REPO_BASE = str(tmpdir)
    return settings.REPO_BASE


def mock_submit(url, body):
    return Mock(content=('%s succ celery-task-id' % body['signature']).encode())


def add_permission(user, perm):
    content_type = ContentType.objects.get_for_model(Experiment)
    permission = Permission.objects.get(
        codename=perm,
        content_type=content_type,
    )
    user.user_permissions.add(permission)


@pytest.mark.django_db
class TestExperimentMatrix:
    @pytest.mark.usefixtures('logged_in_user')
    def test_matrix(self, client, model_with_version, protocol_with_version):
        exp = recipes.experiment.make(model=model_with_version, protocol=protocol_with_version)

        response = client.get('/experiments/matrix')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert str(model_with_version.pk) in data['getMatrix']['models']
        assert str(protocol_with_version.pk) in data['getMatrix']['protocols']
        assert str(exp.pk) in data['getMatrix']['experiments']


@patch('requests.post', side_effect=mock_submit)
@pytest.mark.django_db
class TestNewExperimentView:
    @pytest.mark.usefixtures('logged_in_user')
    def test_submits_experiment(
        self, mock_post,
        client, logged_in_user, model_with_version, protocol_with_version
    ):

        model = model_with_version
        protocol = protocol_with_version
        model_version = model.repo.latest_commit.hexsha
        protocol_version = protocol.repo.latest_commit.hexsha
        add_permission(logged_in_user, 'create_experiment')
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
        assert data['newExperiment']['response']

        version = ExperimentVersion.objects.get()

        assert data['newExperiment']['expId'] == version.experiment.id
        assert data['newExperiment']['versionId'] == version.id
        assert data['newExperiment']['expName'] == version.experiment.name

    @pytest.mark.usefixtures('logged_in_user')
    def test_submit_experiment_requires_permissions(self, mock_post, client, logged_in_user):
        response = client.post('/experiments/new', {})

        assert response.status_code == 200
        data = json.loads(response.content.decode())

        assert not data['newExperiment']['response']
        assert (
            data['newExperiment']['responseText'] ==
            'You are not allowed to create a new experiment'
        )


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
