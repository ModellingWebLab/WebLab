import shutil
from datetime import date
from pathlib import Path

import pytest

from core import recipes


@pytest.fixture
def archive_file_path():
    return str(Path(__file__).absolute().parent.joinpath('./test.omex'))


@pytest.mark.django_db
class TestExperiment:
    def test_name(self, helpers):
        model = recipes.model.make(name='my model')
        protocol = recipes.protocol.make(name='my protocol')
        experiment = recipes.experiment.make(
            model=model,
            model_version=helpers.add_version(model, tag_name='v1').hexsha,
            protocol=protocol,
            protocol_version=helpers.add_version(protocol, tag_name='v2').hexsha,
        )

        assert str(experiment) == experiment.name == 'my model / my protocol'
        assert experiment.get_name() == 'my model / my protocol'
        assert experiment.get_name(model_version=True) == 'my model@v1 / my protocol'
        assert experiment.get_name(proto_version=True) == 'my model / my protocol@v2'

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

    def test_nice_versions(self, experiment_version):
        exp = experiment_version.experiment

        assert exp.nice_model_version == exp.model.repo.latest_commit.hexsha[:8] + '...'
        assert exp.nice_protocol_version == exp.protocol.repo.latest_commit.hexsha[:8] + '...'

        exp.model.repo.tag('v1')
        assert exp.nice_model_version == 'v1'

        exp.protocol.repo.tag('v2')
        assert exp.nice_protocol_version == 'v2'

    def test_visibility(self, helpers):
        model = recipes.model.make()
        protocol = recipes.protocol.make()
        mv1 = helpers.add_version(model, visibility='private').hexsha
        mv2 = helpers.add_version(model, visibility='public').hexsha
        pv1 = helpers.add_version(protocol, visibility='private').hexsha
        pv2 = helpers.add_version(protocol, visibility='public').hexsha

        assert recipes.experiment.make(
            model=model, model_version=mv2,
            protocol=protocol, protocol_version=pv2
        ).visibility == 'public'

        assert recipes.experiment.make(
            model=model, model_version=mv1,
            protocol=protocol, protocol_version=pv1
        ).visibility == 'private'

        assert recipes.experiment.make(
            model=model, model_version=mv1,
            protocol=protocol, protocol_version=pv2
        ).visibility == 'private'


@pytest.mark.django_db
class TestExperimentVersion:
    def test_abs_path(self, fake_experiment_path):
        version = recipes.experiment_version.make(id=2)
        assert str(version.abs_path) == '%s/2' % fake_experiment_path

    def test_archive_path(self, fake_experiment_path):
        version = recipes.experiment_version.make(id=2)
        assert str(version.archive_path) == '%s/2/results.omex' % fake_experiment_path

    def test_signature(self):
        running = recipes.running_experiment.make()
        assert running.experiment_version.signature == str(running.id)

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

    def test_files(self, archive_file_path):
        version = recipes.experiment_version.make()
        version.abs_path.mkdir()
        shutil.copy(archive_file_path, str(version.archive_path))

        assert len(version.files) == 3
        assert version.files[0].name == 'manifest.xml'
        assert version.files[1].name == 'stdout.txt'
        assert version.files[2].name == 'errors.txt'

    def test_files_returns_empty_list_if_no_archive_path(self):
        version = recipes.experiment_version.make()
        assert len(version.files) == 0

    def test_open_file(self, archive_file_path):
        version = recipes.experiment_version.make()
        version.abs_path.mkdir()
        shutil.copy(archive_file_path, str(version.archive_path))

        assert version.open_file('stdout.txt').readline() == b'line of output\n'
