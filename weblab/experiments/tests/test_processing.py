from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile

from core import recipes
from experiments.models import ExperimentVersion
from experiments.processing import (
    ProcessingException,
    process_callback,
    submit_experiment,
)


@pytest.fixture(autouse=True)
def fake_experiment_path(settings, tmpdir):
    settings.EXPERIMENT_BASE = str(tmpdir)
    return settings.EXPERIMENT_BASE


def generate_response(template='%s succ celery-task-id'):
    def mock_submit(url, body):
        return Mock(content=(template % body['signature']).encode())
    return mock_submit


@pytest.fixture
def omex_upload():
    omex_path = str(Path(__file__).absolute().parent.joinpath('./test.omex'))
    with open(omex_path, 'rb') as fp:
        return SimpleUploadedFile('test.omex', fp.read())


@patch('requests.post', side_effect=generate_response())
@pytest.mark.django_db
class TestSubmitExperiment:
    def test_creates_new_experiment(self, mock_post,
                                    model_with_version, protocol_with_version):
        user = recipes.user.make()

        version = submit_experiment(model_with_version, protocol_with_version, user)

        assert version.experiment.model == model_with_version
        assert version.experiment.protocol == protocol_with_version
        assert version.author == user
        assert version.model_version == model_with_version.repo.latest_commit.hexsha
        assert version.protocol_version == protocol_with_version.repo.latest_commit.hexsha
        assert version.experiment.author == user

    def test_uses_existing_experiment(self, mock_post,
                                      model_with_version, protocol_with_version):
        user = recipes.user.make()
        experiment = recipes.experiment.make(
            model=model_with_version,
            protocol=protocol_with_version
        )

        version = submit_experiment(
            model_with_version, protocol_with_version, user
        )

        assert version.experiment == experiment

    def test_submits_to_webservice(self, mock_post, model_with_version, protocol_with_version):
        user = recipes.user.make(full_name='Test User')

        version = submit_experiment(model_with_version, protocol_with_version, user)

        model_url = '/entities/models/%d/versions/%s/archive' % \
            (model_with_version.pk, model_with_version.repo.latest_commit.hexsha)
        protocol_url = '/entities/protocols/%d/versions/%s/archive' % \
            (protocol_with_version.pk, protocol_with_version.repo.latest_commit.hexsha)

        assert mock_post.call_count == 1
        assert mock_post.call_args[0][0] == settings.CHASTE_URL
        assert mock_post.call_args[0][1] == {
            'model': settings.BASE_URL + model_url,
            'protocol': settings.BASE_URL + protocol_url,
            'signature': version.signature,
            'callBack': settings.BASE_URL + '/experiments/callback',
            'user': 'Test User',
            'isAdmin': False,
            'password': settings.CHASTE_PASSWORD,
        }

        assert version.status == ExperimentVersion.STATUS_QUEUED
        assert version.task_id == 'celery-task-id'

    def test_raises_exception_on_webservice_error(self, mock_post,
                                                  model_with_version, protocol_with_version):
        user = recipes.user.make()

        mock_post.side_effect = generate_response('something %s')
        with pytest.raises(ProcessingException):
            submit_experiment(model_with_version, protocol_with_version, user)

    def test_records_submission_error(self, mock_post,
                                      model_with_version, protocol_with_version):
        user = recipes.user.make()
        mock_post.side_effect = generate_response('%s an error occurred')

        version = submit_experiment(model_with_version, protocol_with_version, user)

        assert version.status == ExperimentVersion.STATUS_FAILED
        assert version.return_text == 'an error occurred'

    def test_records_inapplicable_result(self, mock_post,
                                         model_with_version, protocol_with_version):
        user = recipes.user.make()

        mock_post.side_effect = generate_response('%s inapplicable')

        version = submit_experiment(model_with_version, protocol_with_version, user)

        assert version.status == ExperimentVersion.STATUS_INAPPLICABLE


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
            'signature': 1,
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

    def test_records_failed_status(self, queued_experiment, omex_upload):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'failed',
            'returnmsg': 'python stack trace'
        }, {
            'experiment': omex_upload,
        })

        assert result == {'experiment': 'ok'}

        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'FAILED'
        assert queued_experiment.return_text == 'python stack trace'

    def test_default_status_is_success(self, queued_experiment, omex_upload):
        process_callback({
            'signature': queued_experiment.signature,
        }, {
            'experiment': omex_upload,
        })

        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'SUCCESS'

    @pytest.mark.parametrize('returned_status,stored_status', [
        ('success', 'SUCCESS'),
        ('partial', 'PARTIAL'),
    ])
    def test_records_finished_status(self, returned_status, stored_status,
                                     omex_upload, queued_experiment):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': returned_status,
        }, {
            'experiment': omex_upload,
        })

        assert result == {'experiment': 'ok'}

        queued_experiment.refresh_from_db()
        assert queued_experiment.status == stored_status
        assert queued_experiment.return_text == 'finished'

    def test_records_task_id(self, queued_experiment):
        process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'running',
            'taskid': 'task-id-1',
        }, {})

        queued_experiment.refresh_from_db()
        assert queued_experiment.task_id == 'task-id-1'

    def test_stores_archive(self, queued_experiment, omex_upload):
        result = process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'success',
        }, {
            'experiment': omex_upload,
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

    def test_sends_mail_when_experiment_is_finished(self, queued_experiment, omex_upload):
        queued_experiment.author.receive_emails = True
        queued_experiment.author.save()

        process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'success',
        }, {
            'experiment': omex_upload,
        })

        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == 'Web Lab experiment finished'
        assert mail.outbox[0].to[0] == queued_experiment.author.email
        assert 'SUCCESS' in mail.outbox[0].body

    def test_respects_receive_emails_flag(self, queued_experiment, omex_upload):
        queued_experiment.author.receive_emails = False
        queued_experiment.author.save()

        process_callback({
            'signature': queued_experiment.signature,
            'returntype': 'success',
        }, {
            'experiment': omex_upload,
        })

        assert len(mail.outbox) == 0

    def test_overwrites_previous_results(self, queued_experiment, omex_upload):
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
            'experiment': omex_upload,
        })

        assert result == {'experiment': 'ok'}

        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'SUCCESS'
        assert (queued_experiment.abs_path / 'results.omex').exists()
