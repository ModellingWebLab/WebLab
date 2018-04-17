from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from experiments.forms import ExperimentCallbackForm


@pytest.fixture(autouse=True)
def fake_experiment_path(settings, tmpdir):
    settings.EXPERIMENT_BASE = str(tmpdir)
    return settings.EXPERIMENT_BASE


@pytest.mark.django_db
class TestExperimentCallbackForm:
    @pytest.mark.parametrize('returned_status,stored_status', [
        ('success', 'SUCCESS'),
        ('running', 'RUNNING'),
        ('partial', 'PARTIAL'),
        ('inapplicable', 'INAPPLICABLE'),
        ('failed', 'FAILED'),
        ('something else', 'FAILED'),
    ])
    def test_records_status(self, returned_status, stored_status, queued_experiment):
        form = ExperimentCallbackForm({
            'signature': queued_experiment.signature,
            'returntype': returned_status,
        })

        assert form.is_valid()
        assert form.version.status == stored_status

    @pytest.mark.parametrize('status,message', [
        ('inapplicable', 'list, of, missing, terms'),
        ('failed', 'python stacktrace'),
    ])
    def test_records_errormessage(self, status, message, queued_experiment):
        form = ExperimentCallbackForm({
            'signature': queued_experiment.signature,
            'returntype': status,
            'returnmsg': message,
        })

        assert form.is_valid()
        assert form.version.return_text == message

    @pytest.mark.parametrize('status,message', [
        ('success', 'finished'),
        ('partial', 'finished'),
        ('failed', 'finished'),
        ('running', 'running'),
    ])
    def test_records_default_errormessage(self, status, message, queued_experiment):
        form = ExperimentCallbackForm({
            'signature': queued_experiment.signature,
            'returntype': status,
        })

        assert form.is_valid()
        assert form.version.return_text == message

    def test_records_task_id(self, client, queued_experiment):
        form = ExperimentCallbackForm({
            'signature': queued_experiment.signature,
            'returntype': 'running',
            'taskid': 'task-id-1',
        })

        assert form.is_valid()
        assert form.version.task_id == 'task-id-1'

    def test_form_error_on_invalid_signature(self):
        form = ExperimentCallbackForm({
            'signature': 1,
            'returntype': 'success',
        })
        assert not form.is_valid()
        assert 'invalid signature' in form.errors['signature']

    def test_form_error_on_invalid_archive(self, queued_experiment):
        form = ExperimentCallbackForm({
            'signature': queued_experiment.signature,
            'returntype': 'success',
        }, {
            'experiment': SimpleUploadedFile('test.omex', b'hi'),
        })

        assert not form.is_valid()
        assert 'error reading archive: File is not a zip file' in form.errors['experiment']

    def test_saves_experiment_model(self, queued_experiment):
        form = ExperimentCallbackForm({
            'signature': queued_experiment.signature,
            'returntype': 'running',
        })

        assert form.is_valid()

        queued_experiment.refresh_from_db()
        assert queued_experiment.status == 'RUNNING'

    def test_extracts_archive(self, queued_experiment):
        omex_path = Path(__file__).absolute().parent / 'test.omex'
        with omex_path.open('rb') as fp:
            form = ExperimentCallbackForm({
                'signature': queued_experiment.signature,
                'returntype': 'success',
            }, {
                'experiment': SimpleUploadedFile('test.omex', fp.read()),
            })

            assert form.is_valid()

            form.extract_archive()
            assert queued_experiment.abs_path.exists()
            assert (queued_experiment.abs_path / 'errors.txt').exists()
