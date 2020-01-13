import shutil
from datetime import date
from pathlib import Path

import pytest

from core import recipes
from experiments.models import Experiment, ExperimentVersion


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
            model_version=helpers.add_version(model, tag_name='v1').sha,
            protocol=protocol,
            protocol_version=helpers.add_version(protocol, tag_name='v2').sha,
        )

        assert str(experiment) == experiment.name == 'my model / my protocol'
        assert experiment.get_name() == 'my model / my protocol'
        assert experiment.get_name(model_version=True) == 'my model@v1 / my protocol'
        assert experiment.get_name(proto_version=True) == 'my model / my protocol@v2'

    def test_latest_version(self):
        v1 = recipes.experiment_version.make(created_at=date(2017, 1, 2))
        v2 = recipes.experiment_version.make(experiment=v1.experiment, created_at=date(2017, 1, 3))

        assert v1.experiment.latest_version == v2
        assert not v1.is_latest
        assert v2.is_latest

    def test_latest_result(self):
        ver = recipes.experiment_version.make(created_at=date(2017, 1, 2), status='FAILED')

        assert ver.experiment.latest_result == 'FAILED'

    def test_latest_result_empty_if_no_versions(self):
        exp = recipes.experiment.make()

        assert exp.latest_result == ''

    def test_nice_versions(self, experiment_version):
        exp = experiment_version.experiment

        assert exp.nice_model_version == exp.model.repo.latest_commit.sha[:8] + '...'
        assert exp.nice_protocol_version == exp.protocol.repo.latest_commit.sha[:8] + '...'

        exp.model.repo.tag('v1')
        assert exp.nice_model_version == 'v1'

        exp.protocol.repo.tag('v2')
        assert exp.nice_protocol_version == 'v2'

    def test_visibility(self, helpers):
        model = recipes.model.make()
        protocol = recipes.protocol.make()
        mv1 = helpers.add_version(model, visibility='private').sha
        mv2 = helpers.add_version(model, visibility='public').sha
        pv1 = helpers.add_version(protocol, visibility='private').sha
        pv2 = helpers.add_version(protocol, visibility='public').sha

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

    def test_viewers(self, helpers, user):
        helpers.add_permission(user, 'create_model')
        helpers.add_permission(user, 'create_protocol')

        model = recipes.model.make()
        protocol = recipes.protocol.make()
        mv = helpers.add_version(model, visibility='private')
        pv = helpers.add_version(protocol, visibility='private')

        exp = recipes.experiment_version.make(
            experiment__model=model,
            experiment__protocol=protocol,
            experiment__model_version=mv.sha,
            experiment__protocol_version=pv.sha,
        ).experiment
        assert user not in exp.viewers

        exp.model.add_collaborator(user)
        assert user not in exp.viewers

        exp.protocol.add_collaborator(user)
        assert user in exp.viewers

    def test_data_is_deleted_when_experiment_is_deleted(self, experiment_with_result):
        exp_path = experiment_with_result.abs_path

        assert exp_path.exists()

        experiment_with_result.delete()

        assert not exp_path.exists()

    def test_experiment_is_deleted_when_model_is_deleted(self, experiment_with_result):
        experiment_id = experiment_with_result.experiment.id
        version_id = experiment_with_result.id
        exp_path = experiment_with_result.abs_path
        assert exp_path.exists()

        experiment_with_result.experiment.model.delete()

        assert not Experiment.objects.filter(id=experiment_id).exists()
        assert not ExperimentVersion.objects.filter(id=version_id).exists()
        assert not exp_path.exists()


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
        version.mkdir()
        shutil.copy(archive_file_path, str(version.archive_path))

        assert len(version.files) == 4
        assert version.files[0].name == 'manifest.xml'
        assert version.files[1].name == 'stdout.txt'
        assert version.files[2].name == 'errors.txt'
        assert version.files[3].name == 'oxmeta:membrane%3Avoltage - space.csv'

    def test_files_returns_empty_list_if_no_archive_path(self):
        version = recipes.experiment_version.make()
        assert len(version.files) == 0

    def test_open_file(self, archive_file_path):
        version = recipes.experiment_version.make()
        version.mkdir()
        shutil.copy(archive_file_path, str(version.archive_path))

        assert version.open_file('stdout.txt').readline() == b'line of output\n'
