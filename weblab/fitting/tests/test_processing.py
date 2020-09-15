from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from core import recipes
from experiments.models import RunningExperiment
from experiments.processing import ProcessingException
from fitting.models import FittingResult, FittingResultVersion
from fitting.processing import submit_fitting


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
class TestSubmitFitting:
    def test_creates_new_fittingresult_and_side_effects(
            self, mock_post,
            user, model_with_version, protocol_with_version,
            fittingspec_with_version, public_dataset
    ):
        model = model_with_version
        protocol = protocol_with_version
        fittingspec = fittingspec_with_version
        dataset = public_dataset
        model_version = model.repocache.latest_version
        protocol_version = protocol.repocache.latest_version
        fittingspec_version = fittingspec.repocache.latest_version

        assert FittingResult.objects.count() == 0
        assert RunningExperiment.objects.count() == 0

        version, is_new = submit_fitting(
            model_version,
            protocol_version,
            fittingspec_version,
            dataset,
            user,
            False
        )
        assert is_new

        # Check properties of the new fitting result & version
        assert FittingResult.objects.count() == 1
        assert version.fittingresult.model == model
        assert version.fittingresult.protocol == protocol
        assert version.fittingresult.fittingspec == fittingspec
        assert version.fittingresult.dataset == dataset
        assert version.author == user
        assert version.fittingresult.model_version == model_version
        assert version.fittingresult.protocol_version == protocol_version
        assert version.fittingresult.fittingspec_version == fittingspec_version
        assert version.fittingresult.author == user
        assert version.status == FittingResultVersion.STATUS_QUEUED

        # Check it did submit to the webservice
        model_url = '/entities/models/%d/versions/%s/archive' % (model.pk, model_version.sha)
        protocol_url = (
            '/entities/protocols/%d/versions/%s/archive' %
            (protocol.pk, protocol_version.sha))
        fittingspec_url = (
            '/fitting/specs/%d/versions/%s/archive' %
            (fittingspec.pk, fittingspec_version.sha))
        dataset_url = '/datasets/%d/archive' % (dataset.pk)

        assert mock_post.call_count == 1
        assert mock_post.call_args[0][0] == settings.CHASTE_URL
        assert mock_post.call_args[0][1] == {
            'model': settings.CALLBACK_BASE_URL + model_url,
            'protocol': settings.CALLBACK_BASE_URL + protocol_url,
            'fittingSpec': settings.CALLBACK_BASE_URL + fittingspec_url,
            'dataset': settings.CALLBACK_BASE_URL + dataset_url,
            'signature': str(version.running.first().id),
            'callBack': settings.CALLBACK_BASE_URL + '/experiments/callback',
            'user': 'Test User',
            'isAdmin': False,
            'password': settings.CHASTE_PASSWORD,
        }

        # Check running fitting record
        assert RunningExperiment.objects.count() == 1
        assert version.running.count() == 1
        assert version.running.first().task_id == 'celery-task-id'

        # Check the run is cancelled when we delete the fitting result version
        # We check indirect deletion - this should cascade to everything
        mock_post.side_effect = generate_response(field='cancelTask')
        model.delete()
        assert FittingResult.objects.count() == 0
        assert FittingResultVersion.objects.count() == 0
        assert RunningExperiment.objects.count() == 0
        assert mock_post.call_count == 2
        assert mock_post.call_args[0][0] == settings.CHASTE_URL
        assert mock_post.call_args[0][1] == {
            'cancelTask': 'celery-task-id',
            'password': settings.CHASTE_PASSWORD,
        }

    def test_uses_existing_fittingresult(
        self, mock_post, user, model_with_version,
        protocol_with_version, fittingspec_with_version, public_dataset,
    ):
        model = model_with_version
        protocol = protocol_with_version
        fittingspec = fittingspec_with_version
        dataset = public_dataset
        model_version = model.repocache.latest_version
        protocol_version = protocol.repocache.latest_version
        fittingspec_version = fittingspec.repocache.latest_version

        fittingresult = recipes.fittingresult.make(
            model=model, model_version=model_version,
            protocol=protocol, protocol_version=protocol_version,
            fittingspec=fittingspec, fittingspec_version=fittingspec_version,
            dataset=dataset,
        )

        version, is_new = submit_fitting(
            fittingresult.model_version,
            fittingresult.protocol_version,
            fittingresult.fittingspec_version,
            fittingresult.dataset,
            user,
            False,
        )

        assert is_new
        assert version.fittingresult == fittingresult

    def test_raises_exception_on_webservice_error(
        self, mock_post, user, model_with_version, protocol_with_version,
        fittingspec_with_version, public_dataset
    ):
        model = model_with_version
        protocol = protocol_with_version
        fittingspec = fittingspec_with_version
        dataset = public_dataset
        model_version = model.repocache.latest_version
        protocol_version = protocol.repocache.latest_version
        fittingspec_version = fittingspec.repocache.latest_version

        mock_post.side_effect = generate_response('something %s')
        with pytest.raises(ProcessingException):
            submit_fitting(
                model_version,
                protocol_version,
                fittingspec_version,
                dataset,
                user,
                False
            )

        # There should be no running fitting
        assert RunningExperiment.objects.count() == 0

        # It should still record a failed fittingresult version however
        assert FittingResultVersion.objects.count() == 1
        version = FittingResultVersion.objects.first()
        assert version.running.count() == 0
        assert version.fittingresult.model == model
        assert version.fittingresult.protocol == protocol
        assert version.status == FittingResultVersion.STATUS_FAILED
        assert version.return_text.startswith('Chaste backend answered with something unexpected:')

    def test_records_submission_error(
        self, mock_post, user, model_with_version, protocol_with_version,
        fittingspec_with_version, public_dataset
    ):
        model = model_with_version
        protocol = protocol_with_version
        fittingspec = fittingspec_with_version
        dataset = public_dataset
        model_version = model.repocache.latest_version
        protocol_version = protocol.repocache.latest_version
        fittingspec_version = fittingspec.repocache.latest_version

        mock_post.side_effect = generate_response('%s an error occurred')

        version, is_new = submit_fitting(
            model_version,
            protocol_version,
            fittingspec_version,
            dataset,
            user,
            False
        )

        assert is_new
        assert version.status == FittingResultVersion.STATUS_FAILED
        assert version.return_text == 'an error occurred'
        assert RunningExperiment.objects.count() == 0

    def test_records_inapplicable_result(
        self, mock_post, user, model_with_version, protocol_with_version,
        fittingspec_with_version, public_dataset
    ):
        model = model_with_version
        protocol = protocol_with_version
        fittingspec = fittingspec_with_version
        dataset = public_dataset
        model_version = model.repocache.latest_version
        protocol_version = protocol.repocache.latest_version
        fittingspec_version = fittingspec.repocache.latest_version

        mock_post.side_effect = generate_response('%s inapplicable')

        version, is_new = submit_fitting(
            model_version,
            protocol_version,
            fittingspec_version,
            dataset,
            user,
            False
        )

        assert is_new
        assert version.status == FittingResultVersion.STATUS_INAPPLICABLE
        assert RunningExperiment.objects.count() == 0
