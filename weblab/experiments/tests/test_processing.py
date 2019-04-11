import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile

from core import recipes
from experiments.models import Experiment, ExperimentVersion, RunningExperiment
from experiments.processing import (
    ProcessingException,
    process_callback,
    submit_experiment,
)


def generate_response(template='%s succ celery-task-id', field='signature'):
    def mock_submit(url, body):
        return Mock(content=(template % body[field]).encode())
    return mock_submit


@pytest.fixture
def archive_file_path():
    return str(Path(__file__).absolute().parent.joinpath('./test.omex'))


@pytest.fixture
def archive_upload(archive_file_path):
    with open(archive_file_path, 'rb') as fp:
        return SimpleUploadedFile('test.omex', fp.read())


@patch('requests.post', side_effect=generate_response())
@pytest.mark.django_db
class TestSubmitExperiment:
    def test_creates_new_experiment_and_side_effects(
            self, mock_post,
            user, model_with_version, protocol_with_version):
        model = model_with_version
        protocol = protocol_with_version
        model_version = model.repo.latest_commit.hexsha
        protocol_version = protocol.repo.latest_commit.hexsha

        assert Experiment.objects.count() == 0
        assert RunningExperiment.objects.count() == 0

        version = submit_experiment(model, model_version, protocol, protocol_version, user)

        # Check properties of the new experiment & version
        assert Experiment.objects.count() == 1
        assert version.experiment.model == model
        assert version.experiment.protocol == protocol
        assert version.author == user
        assert version.experiment.model_version == model_version
        assert version.experiment.protocol_version == protocol_version
        assert version.experiment.author == user
        assert version.status == ExperimentVersion.STATUS_QUEUED

        # Check it did submit to the webservice
        model_url = '/entities/models/%d/versions/%s/archive' % (model.pk, model_version)
        protocol_url = (
            '/entities/protocols/%d/versions/%s/archive' %
            (protocol.pk, protocol_version))

        assert mock_post.call_count == 1
        assert mock_post.call_args[0][0] == settings.CHASTE_URL
        assert mock_post.call_args[0][1] == {
            'model': settings.CALLBACK_BASE_URL + model_url,
            'protocol': settings.CALLBACK_BASE_URL + protocol_url,
            'signature': str(version.running.first().id),
            'callBack': settings.CALLBACK_BASE_URL + '/experiments/callback',
            'user': 'Test User',
            'isAdmin': False,
            'password': settings.CHASTE_PASSWORD,
        }

        # Check running experiment record
        assert RunningExperiment.objects.count() == 1
        assert version.running.count() == 1
        assert version.running.first().task_id == 'celery-task-id'

        # Check the run is cancelled when we delete the experiment version
        # We check indirect deletion - this should cascade to everything
        mock_post.side_effect = generate_response(field='cancelTask')
        model.delete()
        assert Experiment.objects.count() == 0
        assert ExperimentVersion.objects.count() == 0
        assert RunningExperiment.objects.count() == 0
        assert mock_post.call_count == 2
        assert mock_post.call_args[0][0] == settings.CHASTE_URL
        assert mock_post.call_args[0][1] == {
            'cancelTask': 'celery-task-id',
            'password': settings.CHASTE_PASSWORD,
        }

    def test_uses_existing_experiment(self, mock_post,
                                      user, model_with_version, protocol_with_version):
        model = model_with_version
        protocol = protocol_with_version
        model_version = model.repo.latest_commit.hexsha
        protocol_version = protocol.repo.latest_commit.hexsha

        experiment = recipes.experiment.make(model=model, model_version=model_version,
                                             protocol=protocol, protocol_version=protocol_version)

        version = submit_experiment(model, model_version, protocol, protocol_version, user)

        assert version.experiment == experiment

    def test_raises_exception_on_webservice_error(self, mock_post,
                                                  user, model_with_version, protocol_with_version):
        model = model_with_version
        protocol = protocol_with_version
        model_version = model.repo.latest_commit.hexsha
        protocol_version = protocol.repo.latest_commit.hexsha

        mock_post.side_effect = generate_response('something %s')
        with pytest.raises(ProcessingException):
            submit_experiment(model, model_version, protocol, protocol_version, user)

        # There should be no running experiment
        assert RunningExperiment.objects.count() == 0

        # It should still record a failed experiment version however
        assert ExperimentVersion.objects.count() == 1
        version = ExperimentVersion.objects.first()
        assert version.running.count() == 0
        assert version.experiment.model == model
        assert version.experiment.protocol == protocol
        assert version.status == ExperimentVersion.STATUS_FAILED
        assert version.return_text.startswith('Chaste backend answered with something unexpected:')

    def test_records_submission_error(self, mock_post,
                                      user, model_with_version, protocol_with_version):
        model = model_with_version
        protocol = protocol_with_version
        model_version = model.repo.latest_commit.hexsha
        protocol_version = protocol.repo.latest_commit.hexsha

        mock_post.side_effect = generate_response('%s an error occurred')

        version = submit_experiment(model, model_version, protocol, protocol_version, user)

        assert version.status == ExperimentVersion.STATUS_FAILED
        assert version.return_text == 'an error occurred'
        assert RunningExperiment.objects.count() == 0

    def test_records_inapplicable_result(self, mock_post,
                                         user, model_with_version, protocol_with_version):
        model = model_with_version
        protocol = protocol_with_version
        model_version = model.repo.latest_commit.hexsha
        protocol_version = protocol.repo.latest_commit.hexsha

        mock_post.side_effect = generate_response('%s inapplicable')

        version = submit_experiment(model, model_version, protocol, protocol_version, user)

        assert version.status == ExperimentVersion.STATUS_INAPPLICABLE
        assert RunningExperiment.objects.count() == 0


@pytest.mark.django_db
class TestProcessCallback:
    def test_returns_error_if_no_signature(self):
        result = process_callback({
            'returntype': 'success',
        }, {})
        assert result['error'] == 'missing signature'

    def test_returns_error_on_empty_signature(self):
        result = process_callback({
            'returntype': 'success',
            'signature': '',
        }, {})
        assert result['error'] == 'missing signature'

    def test_returns_error_on_invalid_signature(self):
        result = process_callback({
            'signature': uuid.uuid4(),
            'returntype': 'success',
        }, {})
        assert result['error'] == 'invalid signature'

    def test_records_running_status(self, queued_experiment):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'running',
        }, {})

        assert result == {}

        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'RUNNING'
        assert queued_experiment.return_text == 'running'
        assert queued_experiment.running.count() == 1

    def test_records_inapplicable_status(self, queued_experiment):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'inapplicable',
            'returnmsg': 'experiment cannot be run'
        }, {})

        assert result == {}

        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'INAPPLICABLE'
        assert queued_experiment.return_text == 'experiment cannot be run'
        assert queued_experiment.running.count() == 0

    def test_records_failed_status(self, queued_experiment, archive_upload):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'failed',
            'returnmsg': 'python stack trace'
        }, {
            'experiment': archive_upload,
        })

        assert result == {'experiment': 'ok'}

        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'FAILED'
        assert queued_experiment.return_text == 'python stack trace'

    def test_returns_error_if_no_returntype(self, queued_experiment):
        result = process_callback({
            'signature': queued_experiment.signature,
        }, {})
        assert result['error'] == 'missing returntype'

    def test_returns_error_if_invalid_returntype(self, queued_experiment):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'something invalid',
        }, {})
        assert result['error'] == 'invalid returntype'

    @pytest.mark.parametrize('returned_status,stored_status', [
        ('success', 'SUCCESS'),
        ('partial', 'PARTIAL'),
    ])
    def test_records_finished_status(self, returned_status, stored_status,
                                     archive_upload, queued_experiment):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': returned_status,
        }, {
            'experiment': archive_upload,
        })

        assert result == {'experiment': 'ok'}

        queued_experiment.refresh_from_db()
        assert queued_experiment.status == stored_status
        assert queued_experiment.return_text == 'finished'

    @pytest.mark.parametrize('returned_status', [
        'success',
        'partial',
        'failed',
    ])
    def test_deletes_running_record_when_finished(self, returned_status,
                                                  archive_upload, queued_experiment):
        assert queued_experiment.running.count() == 1

        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': returned_status,
        }, {
            'experiment': archive_upload,
        })

        assert result == {'experiment': 'ok'}

        assert queued_experiment.running.count() == 0

    def test_records_task_id(self, queued_experiment):
        process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'running',
            'taskid': 'task-id-1',
        }, {})

        queued_experiment.refresh_from_db()
        assert queued_experiment.running.first().task_id == 'task-id-1'

    def test_stores_archive(self, queued_experiment, archive_upload):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'success',
        }, {
            'experiment': archive_upload,
        })

        assert result == {'experiment': 'ok'}

        assert (queued_experiment.abs_path / 'results.omex').exists()

    def test_finished_experiment_must_have_attachment(self, queued_experiment):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'success',
            'returnmsg': 'message',
        }, {})

        assert result == {'error': 'no archive found'}
        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'FAILED'
        assert queued_experiment.return_text == 'message (backend returned no archive)'

    def test_returns_error_on_invalid_archive(self, queued_experiment):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'success',
        }, {
            'experiment': SimpleUploadedFile('test.omex', b'hi')
        })

        assert result == {'experiment': 'failed'}
        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'FAILED'
        assert queued_experiment.return_text == 'error reading archive: File is not a zip file'

    def test_sends_mail_when_experiment_is_finished(self, queued_experiment, archive_upload):
        queued_experiment.author.receive_emails = True
        queued_experiment.author.save()

        process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'success',
        }, {
            'experiment': archive_upload,
        })

        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == 'Web Lab experiment finished'
        assert mail.outbox[0].to[0] == queued_experiment.author.email
        assert 'SUCCESS' in mail.outbox[0].body

    def test_respects_receive_emails_flag(self, queued_experiment, archive_upload):
        queued_experiment.author.receive_emails = False
        queued_experiment.author.save()

        process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'success',
        }, {
            'experiment': archive_upload,
        })

        assert len(mail.outbox) == 0

    def test_overwrites_previous_results(self, queued_experiment, archive_upload):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'running',
        }, {})

        assert result == {}
        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'RUNNING'
        assert not (queued_experiment.abs_path / 'results.omex').exists()

        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'success',
        }, {
            'experiment': archive_upload,
        })

        assert result == {'experiment': 'ok'}

        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'SUCCESS'
        assert (queued_experiment.abs_path / 'results.omex').exists()
