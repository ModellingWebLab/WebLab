from unittest.mock import Mock, patch

import pytest
from django.conf import settings

from core import recipes
from experiments.models import ExperimentVersion
from experiments.processing import ProcessingException, submit_experiment


def generate_response(template='%s succ'):
    def mock_submit(url, body):
        return Mock(content=(template % body['signature']).encode())
    return mock_submit


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
            'signature': '%s/experiments/%s' % (settings.BASE_DIR, str(version.id)),
            'callBack': settings.BASE_URL,
            'user': 'Test User',
            'isAdmin': False,
            'password': settings.CHASTE_PASSWORD,
        }

        assert version.status == ExperimentVersion.STATUS_QUEUED

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
