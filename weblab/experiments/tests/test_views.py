import json
import os
import shutil
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
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
class TestExperimentsView:
    @pytest.mark.parametrize("url", [
        '/experiments/',
        '/experiments/models/1/2',
        '/experiments/models/1/2/protocols/3/4',
        '/experiments/protocols/1/2',
        '/experiments/models/1/versions/abc/def',
        '/experiments/models/1/versions/*',
        '/experiments/models/1/versions/abc/def/protocols/3/4',
        '/experiments/protocols/3/versions/abc/def',
        '/experiments/protocols/3/versions/*',
        '/experiments/models/1/2/protocols/3/versions/abc/def',
    ])
    def test_urls(self, client, url):
        """
        This is a dumb page that doesn't actually load any data, so we just
        check that the URLs are working.
        """
        response = client.get(url)

        assert response.status_code == 200


@pytest.mark.django_db
class TestExperimentMatrix:
    @pytest.mark.usefixtures('logged_in_user')
    def test_matrix(self, client, experiment_version):
        exp = experiment_version.experiment

        response = client.get('/experiments/matrix')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert str(exp.model_version) in data['getMatrix']['models']
        assert str(exp.protocol_version) in data['getMatrix']['protocols']
        assert str(exp.pk) in data['getMatrix']['experiments']

    @pytest.mark.usefixtures('logged_in_user')
    def test_experiment_json(self, client, experiment_version):
        exp = experiment_version.experiment

        response = client.get('/experiments/matrix')
        data = json.loads(response.content.decode())

        exp_data = data['getMatrix']['experiments'][str(exp.pk)]
        assert exp_data['id'] == experiment_version.id
        assert exp_data['entity_id'] == exp.id
        assert exp_data['latestResult'] == experiment_version.status
        assert '/experiments/%d/versions/%d' % (exp.id, experiment_version.id) in exp_data['url']

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

    def test_submatrix(self, client, helpers, experiment_version):
        exp = experiment_version.experiment
        other_model = recipes.model.make()
        other_model_version = helpers.add_version(other_model)
        other_protocol = recipes.protocol.make()
        other_protocol_version = helpers.add_version(other_protocol)
        recipes.experiment_version.make(
            experiment__model=other_model,
            experiment__model_version=other_model_version.hexsha,
            experiment__protocol=other_protocol,
            experiment__protocol_version=other_protocol_version.hexsha,
        )

        # Throw in a non-existent protocol so we can make sure it gets ignored
        non_existent_pk = 0
        response = client.get(
            '/experiments/matrix',
            {
                'modelIds[]': [exp.model.pk, non_existent_pk],
                'protoIds[]': [exp.protocol.pk, non_existent_pk],
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        models = data['getMatrix']['models']
        assert len(models) == 1
        assert exp.model_version in models
        assert models[exp.model_version]['id'] == exp.model_version
        assert models[exp.model_version]['entityId'] == exp.model.pk

        protocols = data['getMatrix']['protocols']
        assert len(protocols) == 1
        assert exp.protocol_version in protocols
        assert protocols[exp.protocol_version]['id'] == exp.protocol_version
        assert protocols[exp.protocol_version]['entityId'] == exp.protocol.pk

        experiments = data['getMatrix']['experiments']
        assert len(experiments) == 1
        assert str(exp.pk) in experiments

    def test_submatrix_with_model_versions(self, client, helpers, experiment_version):
        exp = experiment_version.experiment
        v1 = exp.model_version
        v2 = helpers.add_version(exp.model).hexsha
        helpers.add_version(exp.model).hexsha  # v3, not used

        response = client.get(
            '/experiments/matrix',
            {
                'modelIds[]': [exp.model.pk],
                'modelVersions[]': [v1, v2],
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert set(data['getMatrix']['models'].keys()) == {v1, v2}
        assert set(data['getMatrix']['experiments'].keys()) == {str(exp.pk)}

    def test_submatrix_with_all_model_versions(self, client, helpers, experiment_version):
        exp = experiment_version.experiment
        v1 = exp.model_version
        v2 = helpers.add_version(exp.model).hexsha
        v3 = helpers.add_version(exp.model).hexsha

        exp2 = recipes.experiment_version.make(
            experiment__model=exp.model,
            experiment__model_version=v2,
            experiment__protocol=exp.protocol,
            experiment__protocol_version=exp.protocol_version,
        ).experiment

        response = client.get(
            '/experiments/matrix',
            {
                'modelIds[]': [exp.model.pk],
                'modelVersions[]': '*',
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert set(data['getMatrix']['models'].keys()) == {v1, v2, v3}
        assert set(data['getMatrix']['experiments'].keys()) == {str(exp.pk), str(exp2.pk)}

    def test_submatrix_with_too_many_model_ids(self, client, helpers, experiment_version):
        model = recipes.model.make()

        response = client.get(
            '/experiments/matrix',
            {
                'modelIds[]': [experiment_version.experiment.model.pk, model.pk],
                'modelVersions[]': '*',
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert len(data['notifications']['errors']) == 1

    def test_submatrix_with_protocol_versions(self, client, helpers, experiment_version):
        exp = experiment_version.experiment
        v1 = exp.protocol_version
        v2 = helpers.add_version(exp.protocol).hexsha
        helpers.add_version(exp.protocol)  # v3, not used

        exp2 = recipes.experiment_version.make(
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
            experiment__protocol=exp.protocol,
            experiment__protocol_version=v2,
        ).experiment

        response = client.get(
            '/experiments/matrix',
            {
                'protoIds[]': [exp.protocol.pk],
                'protoVersions[]': [v1, v2],
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert set(data['getMatrix']['protocols'].keys()) == {v1, v2}
        assert set(data['getMatrix']['experiments'].keys()) == {str(exp.pk), str(exp2.pk)}

    def test_submatrix_with_all_protocol_versions(self, client, helpers, experiment_version):
        exp = experiment_version.experiment
        v1 = exp.protocol_version
        v2 = helpers.add_version(exp.protocol).hexsha
        v3 = helpers.add_version(exp.protocol).hexsha

        exp2 = recipes.experiment_version.make(
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
            experiment__protocol=exp.protocol,
            experiment__protocol_version=v2,
        ).experiment

        response = client.get(
            '/experiments/matrix',
            {
                'protoIds[]': [exp.protocol.pk],
                'protoVersions[]': '*',
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert set(data['getMatrix']['protocols'].keys()) == {v1, v2, v3}
        assert set(data['getMatrix']['experiments'].keys()) == {str(exp.pk), str(exp2.pk)}

    def test_submatrix_with_too_many_protocol_ids(self, client, helpers, experiment_version):
        protocol = recipes.protocol.make()

        response = client.get(
            '/experiments/matrix',
            {
                'protoIds[]': [experiment_version.experiment.protocol.pk, protocol.pk],
                'protoVersions[]': '*',
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert len(data['notifications']['errors']) == 1

    def test_experiment_without_version_is_ignored(
        self, client, model_with_version, protocol_with_version
    ):
        recipes.experiment.make(
            model=model_with_version,
            model_version=model_with_version.repo.latest_commit.hexsha,
            protocol=protocol_with_version,
            protocol_version=protocol_with_version.repo.latest_commit.hexsha,
        )

        response = client.get('/experiments/matrix')
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert len(data['getMatrix']['protocols']) == 1
        assert len(data['getMatrix']['experiments']) == 0

    def test_old_version_is_hidden(self, client, model_with_version, experiment_version, helpers):
        # Add a new model version without corresponding experiment
        new_version = helpers.add_version(model_with_version, filename='file2.txt')

        # We should now see this version in the matrix, but no experiments
        response = client.get('/experiments/matrix')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data
        assert str(new_version.hexsha) in data['getMatrix']['models']
        assert str(experiment_version.experiment.protocol_version) in data['getMatrix']['protocols']
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
            'signature': uuid.uuid4(),
            'returntype': 'success',
        })

        assert response.status_code == 200

        data = json.loads(response.content.decode())
        assert data['error'] == 'invalid signature'

    def test_doesnt_cause_csrf_errors(self, client):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post('/experiments/callback', {
            'signature': uuid.uuid4(),
            'returntype': 'success',
        })

        assert response.status_code == 200


@pytest.mark.django_db
class TestExperimentVersionsView:
    def test_view_experiment_versions(self, client, experiment_version):
        response = client.get(
            ('/experiments/%d/versions/' % experiment_version.experiment.pk)
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
class TestExperimentComparisonView:
    def test_compare_experiments(self, client, experiment_version, helpers):
        exp = experiment_version.experiment
        protocol = recipes.protocol.make()
        protocol_commit = helpers.add_version(protocol)

        version2 = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
            experiment__protocol=protocol,
            experiment__protocol_version=protocol_commit.hexsha,
        )

        response = client.get(
            ('/experiments/compare/%d/%d' % (experiment_version.id, version2.id))
        )

        assert response.status_code == 200
        assert set(response.context['experiment_versions']) == {
            experiment_version, version2
        }

    def test_only_compare_visible_experiments(self, client, experiment_version, helpers):
        ver1 = experiment_version
        exp = ver1.experiment

        proto = recipes.protocol.make(visibility='private')
        proto_commit = helpers.add_version(proto)
        ver2 = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
            experiment__protocol=proto,
            experiment__protocol_version=proto_commit.hexsha,
        )

        response = client.get(
            ('/experiments/compare/%d/%d' % (ver1.id, ver2.id))
        )

        assert response.status_code == 200
        assert set(response.context['experiment_versions']) == {ver1}

        assert len(response.context['ERROR_MESSAGES']) == 1

    def test_no_visible_experiments(self, client, experiment_version):
        proto = experiment_version.experiment.protocol
        proto.visibility = 'private'
        proto.save()
        assert experiment_version.visibility == 'private'

        response = client.get('/experiments/compare/%d' % (experiment_version.id))

        assert response.status_code == 200
        assert len(response.context['experiment_versions']) == 0


@pytest.mark.django_db
class TestExperimentComparisonJsonView:
    def test_compare_experiments(self, client, experiment_version, helpers):
        exp = experiment_version.experiment
        protocol = recipes.protocol.make()
        protocol_commit = helpers.add_version(protocol)
        exp.protocol.repo.tag('v1')

        version2 = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
            experiment__protocol=protocol,
            experiment__protocol_version=protocol_commit.hexsha,
        )

        response = client.get(
            ('/experiments/compare/%d/%d/info' % (experiment_version.id, version2.id))
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        versions = data['getEntityInfos']['entities']
        assert versions[0]['versionId'] == experiment_version.id
        assert versions[1]['versionId'] == version2.id
        assert versions[0]['modelName'] == exp.model.name
        assert versions[0]['modelVersion'] == exp.model_version
        assert versions[0]['protoName'] == exp.protocol.name
        assert versions[0]['protoVersion'] == 'v1'
        assert versions[0]['name'] == exp.name
        assert versions[0]['runNumber'] == 1

    def test_only_compare_visible_experiments(self, client, experiment_version, helpers):
        ver1 = experiment_version
        exp = ver1.experiment

        proto = recipes.protocol.make(visibility='private')
        proto_commit = helpers.add_version(proto)
        ver2 = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
            experiment__protocol=proto,
            experiment__protocol_version=proto_commit.hexsha,
        )

        response = client.get(
            ('/experiments/compare/%d/%d/info' % (ver1.id, ver2.id))
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        versions = data['getEntityInfos']['entities']
        assert len(versions) == 1
        assert versions[0]['versionId'] == ver1.id

    def test_file_json(self, client, archive_file_path, helpers):
        version = recipes.experiment_version.make(
            author__full_name='test user',
            experiment__model_version='latest',
            experiment__protocol_version='latest')
        version.abs_path.mkdir()
        shutil.copyfile(archive_file_path, str(version.archive_path))
        exp = version.experiment

        protocol = recipes.protocol.make()
        protocol_commit = helpers.add_version(protocol)
        version2 = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
            experiment__protocol=protocol,
            experiment__protocol_version=protocol_commit.hexsha,
        )
        version2.abs_path.mkdir()
        shutil.copyfile(archive_file_path, str(version2.archive_path))

        response = client.get(
            ('/experiments/compare/%d/%d/info' % (version.pk, version2.pk))
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        file1 = data['getEntityInfos']['entities'][0]['files'][0]
        assert file1['author'] == 'test user'
        assert file1['name'] == 'stdout.txt'
        assert file1['filetype'] == 'http://purl.org/NET/mediatypes/text/plain'
        assert not file1['masterFile']
        assert file1['size'] == 27
        assert file1['url'] == (
            '/experiments/%d/versions/%d/download/stdout.txt' % (exp.pk, version.pk)
        )

    def test_empty_experiment_list(self, client, experiment_version):
        response = client.get('/experiments/compare/info')

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert len(data['getEntityInfos']['entities']) == 0


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
        file1 = data['version']['files'][0]
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
    def test_download_archive(self, client, experiment_version, archive_file_path):
        experiment_version.abs_path.mkdir(exist_ok=True)
        shutil.copyfile(archive_file_path, str(experiment_version.archive_path))
        experiment_version.experiment.model.name = 'my_model'
        experiment_version.experiment.model.save()
        experiment_version.experiment.protocol.name = 'my_protocol'
        experiment_version.experiment.protocol.save()

        response = client.get(
            '/experiments/%d/versions/%d/archive' %
            (experiment_version.experiment.pk, experiment_version.pk)
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
        version.abs_path.mkdir(exist_ok=True)
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


@pytest.mark.django_db
class TestExperimentSimulateCallbackView:
    @patch('experiments.views.process_callback')
    def test_processes_callback_if_form_valid(
        self, mock_process,
        client, logged_in_admin, queued_experiment, archive_file
    ):
        mock_process.return_value = {}

        version = queued_experiment
        response = client.post(
            '/experiments/%d/versions/%d/callback' % (version.experiment.id, version.id),
            {
                'returntype': 'success',
                'returnmsg': 'experiment was successful',
                'upload': archive_file
            }
        )

        assert response.status_code == 302
        assert response.url == '/experiments/%d/versions/%d' % (version.experiment.id, version.id)
        assert mock_process.call_count == 1
        assert mock_process.call_args[0][0]['returntype'] == 'success'
        assert mock_process.call_args[0][0]['returnmsg'] == 'experiment was successful'
        assert archive_file.name.endswith(mock_process.call_args[0][1]['experiment'].name)

        messages = list(get_messages(response.wsgi_request))
        assert messages[0].level_tag == 'info'

    @patch('experiments.views.process_callback')
    def test_exposes_processing_error(
        self, mock_process,
        client, logged_in_admin, queued_experiment, archive_file
    ):
        mock_process.return_value = {'error': 'processing error'}
        version = queued_experiment
        response = client.post(
            '/experiments/%d/versions/%d/callback' % (version.experiment.id, version.id),
            {
                'returntype': 'success',
                'returnmsg': 'experiment was successful',
                'upload': archive_file
            }
        )

        assert response.status_code == 302
        assert response.url == '/experiments/%d/versions/%d' % (version.experiment.id, version.id)
        assert mock_process.call_count == 1

        messages = list(get_messages(response.wsgi_request))
        assert messages[0].level_tag == 'error'
        assert str(messages[0]) == 'processing error'
