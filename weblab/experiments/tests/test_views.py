import json
import os
import shutil
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.utils.dateparse import parse_datetime

from core import recipes
from core.visibility import Visibility
from experiments.models import Experiment, ExperimentVersion


def mock_submit(url, body):
    return Mock(content=('%s succ celery-task-id' % body['signature']).encode())


def add_permission(user, perm):
    content_type = ContentType.objects.get_for_model(Experiment)
    permission = Permission.objects.get(
        codename=perm,
        content_type=content_type,
    )
    user.user_permissions.add(permission)


@pytest.fixture
def archive_file_path():
    return str(Path(__file__).absolute().parent.joinpath('./test.omex'))


@pytest.yield_fixture
def archive_file(archive_file_path):
    with open(archive_file_path, 'rb') as fp:
        yield fp


@pytest.mark.django_db
class TestExperimentMatrix:
    @pytest.mark.usefixtures('logged_in_user')
    def test_matrix(self, client, experiment_version):
        exp = experiment_version.experiment

        response = client.get('/experiments/matrix')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert str(exp.model.pk) in data['getMatrix']['models']
        assert str(exp.protocol.pk) in data['getMatrix']['protocols']
        assert str(exp.pk) in data['getMatrix']['experiments']

    def test_anonymous_can_see_public_data(self, client, experiment_version):
        response = client.get('/experiments/matrix')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data
        assert str(experiment_version.experiment.pk) in data['getMatrix']['experiments']

    def test_anonymous_cannot_see_private_data(self, client, experiment_version):
        model = experiment_version.experiment.model
        model.visibility = Visibility.PRIVATE
        model.save()

        response = client.get('/experiments/matrix')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data
        assert len(data['getMatrix']['models']) == 0
        assert len(data['getMatrix']['protocols']) == 1
        assert len(data['getMatrix']['experiments']) == 0

    def test_old_version_is_hidden(self, client, model_with_version, experiment_version, helpers):
        # Add a new model version without corresponding experiment
        helpers.add_version(model_with_version, filename='file2.txt')

        # We should now see this version in the matrix, but no experiments
        response = client.get('/experiments/matrix')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data
        assert str(model_with_version.pk) in data['getMatrix']['models']
        assert str(experiment_version.experiment.protocol.pk) in data['getMatrix']['protocols']
        assert len(data['getMatrix']['experiments']) == 0


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

    @pytest.mark.usefixtures('logged_in_user')
    def test_rerun_experiment(
        self, mock_post,
        client, logged_in_user, experiment_version
    ):
        add_permission(logged_in_user, 'create_experiment')
        response = client.post(
            '/experiments/new',
            {
                'rerun': experiment_version.pk,
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())

        assert 'newExperiment' in data
        assert data['newExperiment']['response']
        assert data['newExperiment']['expId'] == experiment_version.experiment.id

        assert ExperimentVersion.objects.count() == 2
        new_version = ExperimentVersion.objects.all().last()

        assert new_version.experiment.id == experiment_version.experiment.id
        assert new_version.id != experiment_version.id
        assert data['newExperiment']['versionId'] == new_version.id
        assert data['newExperiment']['expName'] == new_version.experiment.name


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

    def test_doesnt_cause_csrf_errors(self, client):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post('/experiments/callback', {
            'signature': 1,
            'returntype': 'success',
        })

        assert response.status_code == 200


@pytest.mark.django_db
class TestExperimentVersionsView:
    def test_view_experiment_versions(self, client, experiment_version):
        response = client.get(
            ('/experiments/%d/versions' % experiment_version.experiment.pk)
        )

        assert response.status_code == 200
        assert response.context['experiment'] == experiment_version.experiment


@pytest.mark.django_db
class TestExperimentVersionView:
    def test_view_experiment_version(self, client, experiment_version):
        response = client.get(
            ('/experiments/%d/versions/%d' % (experiment_version.experiment.pk,
                                              experiment_version.pk))
        )

        assert response.status_code == 200
        assert response.context['version'] == experiment_version


@pytest.mark.django_db
class TestExperimentVersionJsonView:
    def test_experiment_json(self, client):
        version = recipes.experiment_version.make(
            author__full_name='test user',
            status='SUCCESS',
            experiment__model_version='latest',
            experiment__protocol_version='latest',
        )

        response = client.get(
            ('/experiments/%d/versions/%d/files.json' % (version.experiment.pk, version.pk))
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        ver = data['version']
        assert ver['id'] == version.pk
        assert ver['author'] == 'test user'
        assert ver['status'] == 'SUCCESS'
        assert ver['visibility'] == 'public'
        assert (
            parse_datetime(ver['created']).replace(microsecond=0) ==
            version.created_at.replace(microsecond=0)
        )
        assert ver['name'] == '1'
        assert ver['experimentId'] == version.experiment.id
        assert ver['version'] == version.id
        assert ver['files'] == []
        assert ver['numFiles'] == 0
        assert ver['download_url'] == (
            '/experiments/%d/versions/%d/archive' % (version.experiment.pk, version.pk)
        )

    def test_file_json(self, client, archive_file_path):
        version = recipes.experiment_version.make(
            author__full_name='test user',
            experiment__model_version='latest',
            experiment__protocol_version='latest')
        version.abs_path.mkdir()
        shutil.copyfile(archive_file_path, str(version.archive_path))

        response = client.get(
            ('/experiments/%d/versions/%d/files.json' % (version.experiment.pk, version.pk))
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        file1 = data['version']['files'][1]
        assert file1['author'] == 'test user'
        assert file1['name'] == 'stdout.txt'
        assert file1['filetype'] == 'http://purl.org/NET/mediatypes/text/plain'
        assert not file1['masterFile']
        assert file1['size'] == 27
        assert file1['url'] == (
            '/experiments/%d/versions/%d/download/stdout.txt' % (version.experiment.pk, version.pk)
        )


@pytest.mark.django_db
class TestExperimentArchiveView:
    def test_download_archive(self, client, archive_file_path):
        version = recipes.experiment_version.make(
            experiment__model__name='my model',
            experiment__protocol__name='my protocol',
        )
        version.abs_path.mkdir()
        shutil.copyfile(archive_file_path, str(version.archive_path))

        response = client.get(
            '/experiments/%d/versions/%d/archive' % (version.experiment.pk, version.pk)
        )
        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert set(archive.namelist()) == {'stdout.txt', 'errors.txt', 'manifest.xml'}
        assert response['Content-Disposition'] == (
            'attachment; filename=my_model__my_protocol.zip'
        )

    def test_returns_404_if_no_archive_exists(self, client):
        version = recipes.experiment_version.make()

        response = client.get(
            '/experiments/%d/versions/%d/archive' % (version.experiment.pk, version.pk)
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestExperimentFileDownloadView:
    def test_download_file(self, client, archive_file_path):
        version = recipes.experiment_version.make()
        version.abs_path.mkdir()
        shutil.copyfile(archive_file_path, str(version.archive_path))

        response = client.get(
            '/experiments/%d/versions/%d/download/stdout.txt' % (version.experiment.pk, version.pk)
        )
        assert response.status_code == 200
        assert response.content == b'line of output\nmore output\n'
        assert response['Content-Disposition'] == (
            'attachment; filename=stdout.txt'
        )
        assert response['Content-Type'] == 'text/plain'


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
        client, logged_in_user, archive_file_path, experiment_version,
        url
    ):
        experiment_version.author = logged_in_user
        experiment_version.experiment.model.visibility = 'private'
        experiment_version.save()
        experiment_version.experiment.model.save()
        os.mkdir(str(experiment_version.abs_path))
        shutil.copyfile(archive_file_path, str(experiment_version.archive_path))

        exp_url = url % (experiment_version.experiment.pk, experiment_version.pk)
        assert client.get(exp_url, follow=True).status_code == 200

    @pytest.mark.usefixtures('logged_in_user')
    def test_private_expt_invisible_to_other_user(self, client, other_user,
                                                  experiment_version, url):
        experiment_version.author = other_user
        experiment_version.experiment.protocol.visibility = 'private'
        experiment_version.save()
        experiment_version.experiment.protocol.save()

        exp_url = url % (experiment_version.experiment.pk, experiment_version.pk)
        response = client.get(exp_url)
        assert response.status_code == 404

    def test_private_entity_requires_login_for_anonymous(self, client, experiment_version, url):
        experiment_version.experiment.model.visibility = 'private'
        experiment_version.experiment.model.save()

        exp_url = url % (experiment_version.experiment.pk, experiment_version.pk)
        response = client.get(exp_url)
        assert response.status_code == 302
        assert '/login' in response.url
