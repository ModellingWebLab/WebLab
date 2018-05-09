import json
import os
import shutil
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


@pytest.fixture
def test_archive_path():
    return str(Path(__file__).absolute().parent.joinpath('./test.omex'))


@pytest.yield_fixture
def archive_file(test_archive_path):
    with open(test_archive_path, 'rb') as fp:
        yield fp


@pytest.mark.django_db
class TestExperimentCallbackView:
    def test_saves_valid_experiment_results(self, client, queued_experiment, archive_file):
        response = client.post('/experiments/callback', {
            'signature': queued_experiment.signature,
            'returntype': 'success',
            'experiment': archive_file,
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


@pytest.mark.django_db
@pytest.mark.parametrize("url", [
    ('/experiments/%d/versions/%d'),
    ('/experiments/%d/versions/%d/files.json'),
    ('/experiments/%d/versions/%d/download/stdout.txt'),
    ('/experiments/%d/versions/%d/archive'),
])
class TestEnforcesExperimentVersionVisibility:
    """
    Visibility logic is fully tested in TestEntityVisibility
    """
    def test_private_expt_visible_to_self(
        self,
        client, logged_in_user, test_archive_path, experiment,
        url
    ):
        experiment.author = logged_in_user
        experiment.visibility = 'private'
        experiment.save()
        os.mkdir(str(experiment.abs_path))
        shutil.copyfile(test_archive_path, str(experiment.archive_path))

        exp_url = url % (experiment.experiment.pk, experiment.pk)
        assert client.get(exp_url, follow=True).status_code == 200

    @pytest.mark.usefixtures('logged_in_user')
    def test_private_expt_invisible_to_other_user(self, client, other_user, experiment, url):
        experiment.author = other_user
        experiment.visibility = 'private'
        experiment.save()

        exp_url = url % (experiment.experiment.pk, experiment.pk)
        response = client.get(exp_url)
        assert response.status_code == 404

    def test_private_entity_requires_login_for_anonymous(self, client, experiment, url):
        experiment.visibility = 'private'
        experiment.save()

        exp_url = url % (experiment.experiment.pk, experiment.pk)
        response = client.get(exp_url)
        assert response.status_code == 302
        assert '/login' in response.url
