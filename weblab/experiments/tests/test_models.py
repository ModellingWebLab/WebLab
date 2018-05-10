import shutil
from datetime import date
from pathlib import Path

import pytest

from core import recipes


@pytest.fixture
def test_archive_path():
    return str(Path(__file__).absolute().parent.joinpath('./test.omex'))


@pytest.mark.django_db
class TestExperiment:
    def test_name(self):
        experiment = recipes.experiment.make(
            model__name='my model',
            protocol__name='my protocol'
        )

        assert str(experiment) == experiment.name == 'my model / my protocol'

    def test_latest_version(self):
        v1 = recipes.experiment_version.make(created_at=date(2017, 1, 2))
        v2 = recipes.experiment_version.make(experiment=v1.experiment, created_at=date(2017, 1, 3))

        assert v1.experiment.latest_version == v2

    def test_latest_result(self):
        ver = recipes.experiment_version.make(created_at=date(2017, 1, 2), status='FAILED')

        assert ver.experiment.latest_result == 'FAILED'

    def test_latest_result_empty_if_no_versions(self):
        exp = recipes.experiment.make()

        assert exp.latest_result == ''


@pytest.mark.django_db
class TestExperimentVersion:
    def test_abs_path(self, fake_experiment_path):
        version = recipes.experiment_version.make(id=2)
        assert str(version.abs_path) == '%s/2' % fake_experiment_path

    def test_archive_path(self, fake_experiment_path):
        version = recipes.experiment_version.make(id=2)
        assert str(version.archive_path) == '%s/2/results.omex' % fake_experiment_path

    def test_signature(self):
        version = recipes.experiment_version.make(id=2)
        assert version.signature == '2'

    @pytest.mark.parametrize('status, is_running', [
        ('QUEUED', False),
        ('RUNNING', True),
        ('SUCCESS', False),
        ('PARTIAL', False),
        ('FAILED', False),
        ('INAPPLICABLE', False),
    ])
    def test_is_running(self, status, is_running):
        version = recipes.experiment_version.make(status=status)
        assert version.is_running == is_running

    @pytest.mark.parametrize('status, is_finished', [
        ('QUEUED', False),
        ('RUNNING', False),
        ('SUCCESS', True),
        ('PARTIAL', True),
        ('FAILED', True),
        ('INAPPLICABLE', False),
    ])
    def test_is_finished(self, status, is_finished):
        version = recipes.experiment_version.make(status=status)
        assert version.is_finished == is_finished

    def test_update_status(self):
        version = recipes.experiment_version.make(status='RUNNING')

        version.update('SUCCESS', 'successful experiment')
        version.refresh_from_db()
        assert version.status == 'SUCCESS'
        assert version.return_text == 'successful experiment'

    def test_files(self, test_archive_path):
        version = recipes.experiment_version.make()
        version.abs_path.mkdir()
        shutil.copy(test_archive_path, str(version.archive_path))

        assert len(version.files) == 3
        assert version.files[0].name == 'manifest.xml'
        assert version.files[1].name == 'stdout.txt'
        assert version.files[2].name == 'errors.txt'

    def test_files_returns_empty_list_if_no_archive_path(self):
        version = recipes.experiment_version.make()
        assert len(version.files) == 0

    def test_open_file(self, test_archive_path):
        version = recipes.experiment_version.make()
        version.abs_path.mkdir()
        shutil.copy(test_archive_path, str(version.archive_path))

        assert version.open_file('stdout.txt').readline() == b'line of output\n'
