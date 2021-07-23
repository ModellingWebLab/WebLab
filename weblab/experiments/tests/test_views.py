import json
import shutil
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from core import recipes
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from experiments.models import (
    Experiment,
    ExperimentVersion,
    PlannedExperiment,
    RunningExperiment,
)
from pytest_django.asserts import assertContains, assertTemplateUsed
from repocache.populate import populate_entity_cache


def generate_response(template='%s succ celery-task-id'):
    def mock_submit(url, body):
        return Mock(content=(template % body['signature']).encode())
    return mock_submit


def add_permission(user, perm):
    content_type = ContentType.objects.get_for_model(Experiment)
    permission = Permission.objects.get(
        codename=perm,
        content_type=content_type,
    )
    user.user_permissions.add(permission)


def make_experiment(model, model_version, protocol, protocol_version):
    """Create an experiment in the DB with a single version."""
    exp = recipes.experiment.make(
        model=model, model_version=model_version,
        protocol=protocol, protocol_version=protocol_version)
    recipes.experiment_version.make(experiment=exp)
    return exp


@pytest.fixture
def archive_file_path():
    return str(Path(__file__).absolute().parent.joinpath('./test.omex'))


@pytest.yield_fixture
def archive_file(archive_file_path):
    with open(archive_file_path, 'rb') as fp:
        yield fp


@pytest.fixture
def planned_experiments(model_with_version, protocol_with_version):
    """Fill in DB for NewExperimentView tests."""
    model = model_with_version
    protocol = protocol_with_version
    model_version = model.repo.latest_commit.sha
    protocol_version = protocol.repo.latest_commit.sha
    PlannedExperiment(
        model=model,
        protocol=protocol,
        model_version=model_version,
        protocol_version=protocol_version
    ).save()
    PlannedExperiment(
        model=model,
        protocol=protocol,
        model_version=uuid.uuid4(),
        protocol_version=uuid.uuid4()
    ).save()
    PlannedExperiment(
        model=model,
        protocol=recipes.protocol.make(),
        model_version=model_version,
        protocol_version=uuid.uuid4()
    ).save()
    PlannedExperiment(
        model=recipes.model.make(),
        protocol=protocol,
        model_version=uuid.uuid4(),
        protocol_version=protocol_version
    ).save()
    PlannedExperiment(
        model=recipes.model.make(),
        protocol=recipes.protocol.make(),
        model_version=uuid.uuid4(),
        protocol_version=uuid.uuid4()
    ).save()
    return PlannedExperiment.objects.count()


@pytest.mark.django_db
class TestExperimentsView:
    @pytest.mark.parametrize("url", [
        '/experiments/',
        '/experiments/mine',
        '/experiments/public/models/1/2',
        '/experiments/all/protocols/1/2',
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
    def test_matrix_json(self, client, quick_experiment_version):
        exp = quick_experiment_version.experiment

        response = client.get('/experiments/matrix?subset=all')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert len(data['getMatrix']['rows']) == 1
        assert str(exp.model_version.sha) in data['getMatrix']['rows']
        assert len(data['getMatrix']['columns']) == 1
        assert str(exp.protocol_version.sha) in data['getMatrix']['columns']
        assert len(data['getMatrix']['experiments']) == 1
        assert str(exp.pk) in data['getMatrix']['experiments']

        exp_data = data['getMatrix']['experiments'][str(exp.pk)]
        assert exp_data['id'] == quick_experiment_version.id
        assert exp_data['entity_id'] == exp.id
        assert exp_data['latestResult'] == quick_experiment_version.status
        assert '/experiments/%d/versions/%d' % (exp.id, quick_experiment_version.id) in exp_data['url']

    def test_anonymous_can_see_public_data(self, client, quick_experiment_version):
        response = client.get('/experiments/matrix?subset=all')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data
        assert str(quick_experiment_version.experiment.pk) in data['getMatrix']['experiments']

    def test_anonymous_cannot_see_private_data(self, client, quick_experiment_version):
        model = quick_experiment_version.experiment.model
        version = model.repocache.latest_version
        version.visibility = 'private'
        version.save()

        response = client.get('/experiments/matrix?subset=all')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data
        assert len(data['getMatrix']['rows']) == 0
        assert len(data['getMatrix']['columns']) == 1
        assert len(data['getMatrix']['experiments']) == 0

    def test_view_my_experiments_with_moderated_flags(
        self, client, helpers, logged_in_user, quick_experiment_version,
        moderated_model, moderated_protocol, moderated_experiment_version
    ):
        my_model = recipes.model.make(author=logged_in_user)
        my_model_version = helpers.add_fake_version(my_model, visibility='private')
        my_protocol = recipes.protocol.make(author=logged_in_user)
        my_protocol_version = helpers.add_fake_version(my_protocol, visibility='private')

        my_moderated_model = recipes.model.make(author=logged_in_user)
        helpers.add_fake_version(my_moderated_model, visibility='moderated')
        my_moderated_protocol = recipes.protocol.make(author=logged_in_user)
        helpers.add_fake_version(my_moderated_protocol, visibility='moderated')

        my_version = make_experiment(my_model, my_model_version, my_protocol, my_protocol_version)
        with_moderated_model = make_experiment(
            moderated_model, moderated_model.repocache.latest_version,
            my_protocol, my_protocol_version,
        )
        with_moderated_protocol = make_experiment(
            my_model, my_model_version,
            moderated_protocol, moderated_protocol.repocache.latest_version,
        )
        with_my_moderated_model = make_experiment(
            my_moderated_model, my_moderated_model.repocache.latest_version,
            my_protocol, my_protocol_version,
        )
        with_my_moderated_protocol = make_experiment(
            my_model, my_model_version,
            my_moderated_protocol, my_moderated_protocol.repocache.latest_version,
        )

        # All my experiments plus ones involving moderated entities
        response = client.get('/experiments/matrix?subset=mine')
        data = json.loads(response.content.decode())
        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(my_version.pk),
            str(with_moderated_model.pk),
            str(with_moderated_protocol.pk),
            str(moderated_experiment_version.experiment.pk),
            str(with_my_moderated_model.pk),
            str(with_my_moderated_protocol.pk),
        }

        # Exclude those involving moderated protocols
        response = client.get('/experiments/matrix?subset=mine&moderated-protocols=false')
        data = json.loads(response.content.decode())
        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(my_version.pk),
            str(with_moderated_model.pk),
            str(with_my_moderated_model.pk),
        }

        # Exclude those involving moderated models
        response = client.get('/experiments/matrix?subset=mine&moderated-models=false')
        data = json.loads(response.content.decode())
        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(my_version.pk),
            str(with_moderated_protocol.pk),
            str(with_my_moderated_protocol.pk),
        }

        # Don't show anything moderated
        response = client.get('/experiments/matrix?subset=mine&moderated-models=false&moderated-protocols=false')
        data = json.loads(response.content.decode())
        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(my_version.pk),
        }

    def test_view_my_experiments_empty_for_anonymous(self, client, helpers, quick_experiment_version):
        response = client.get('/experiments/matrix?subset=mine')
        data = json.loads(response.content.decode())

        assert len(data['getMatrix']['experiments']) == 0

    def test_view_public_experiments(self, client, logged_in_user, other_user, helpers):
        # My moderated model with my private protocol: should not be visible
        my_model_moderated = recipes.model.make(author=logged_in_user)
        my_model_moderated_version = helpers.add_fake_version(my_model_moderated, visibility='moderated')

        my_protocol_private = recipes.protocol.make(author=logged_in_user)
        my_protocol_private_version = helpers.add_fake_version(my_protocol_private, visibility='private')

        exp1 = make_experiment(
            my_model_moderated, my_model_moderated_version,
            my_protocol_private, my_protocol_private_version,
        )

        # Someone else's public model with my public protocol: should be visible
        # But experiments with newer private versions should not be
        other_model_public = recipes.model.make(author=other_user)
        other_model_public_version = helpers.add_fake_version(other_model_public, visibility='public')
        other_model_second_private_version = helpers.add_fake_version(other_model_public, visibility='private')

        my_protocol_public = recipes.protocol.make(author=logged_in_user)
        my_protocol_public_version = helpers.add_fake_version(my_protocol_public, visibility='public')
        my_protocol_second_private_version = helpers.add_fake_version(my_protocol_public, visibility='private')

        exp2 = make_experiment(
            other_model_public, other_model_public_version,
            my_protocol_public, my_protocol_public_version,
        )
        exp2_model_private = make_experiment(  # noqa: F841
            other_model_public, other_model_second_private_version,
            my_protocol_public, my_protocol_public_version,
        )
        exp2_protocol_private = make_experiment(
            other_model_public, other_model_public_version,
            my_protocol_public, my_protocol_second_private_version,
        )

        # Someone else's public model and moderated protocol: should be visible
        other_protocol_moderated = recipes.protocol.make(author=other_user)
        other_protocol_moderated_version = helpers.add_fake_version(other_protocol_moderated, visibility='moderated')
        other_protocol_private_version = helpers.add_fake_version(other_protocol_moderated, visibility='private')

        exp3 = make_experiment(
            other_model_public, other_model_public_version,
            other_protocol_moderated, other_protocol_moderated_version,
        )
        exp3_protocol_private = make_experiment(
            other_model_public, other_model_second_private_version,
            other_protocol_moderated, other_protocol_private_version,
        )

        # Other's private model, my public protocol: should not be visible
        other_model_private = recipes.model.make(author=other_user)
        other_model_private_version = helpers.add_fake_version(other_model_private, visibility='private')

        exp4 = make_experiment(  # noqa: F841
            other_model_private, other_model_private_version,
            my_protocol_public, my_protocol_public_version,
        )

        response = client.get('/experiments/matrix?subset=public')
        data = json.loads(response.content.decode())

        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(exp2.pk),
            str(exp3.pk),
        }

        # If however I ask for what I can see, I get more returned
        response = client.get('/experiments/matrix?subset=all')
        data = json.loads(response.content.decode())

        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(exp1.pk),
            str(exp2_protocol_private.pk),
            str(exp3.pk),
        }

        # If the other user shares with me, I see their later private versions instead
        other_model_public.add_collaborator(logged_in_user)
        other_protocol_moderated.add_collaborator(logged_in_user)
        response = client.get('/experiments/matrix?subset=all')
        data = json.loads(response.content.decode())

        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(exp1.pk),
            str(exp3_protocol_private.pk),
        }

    def test_view_moderated_experiments(self, client, logged_in_user, other_user, helpers):
        # My public model with somebody else's public protocol: should not be visible
        my_model_public = recipes.model.make(author=logged_in_user)
        my_model_public_version = helpers.add_fake_version(my_model_public, visibility='public')

        other_protocol_public = recipes.protocol.make(author=other_user)
        other_protocol_public_version = helpers.add_fake_version(other_protocol_public, visibility='public')

        exp1 = make_experiment(
            my_model_public, my_model_public_version,
            other_protocol_public, other_protocol_public_version,
        )

        # My public model with somebody else's moderated protocol: should not be visible
        other_protocol_moderated = recipes.protocol.make(author=other_user)
        other_protocol_moderated_version = helpers.add_fake_version(other_protocol_moderated, visibility='moderated')

        exp2 = make_experiment(
            my_model_public, my_model_public_version,
            other_protocol_moderated, other_protocol_moderated_version,
        )

        # Someone else's moderated model and public protocol: should not be visible
        other_model_moderated = recipes.model.make(author=other_user)
        other_model_moderated_version = helpers.add_fake_version(other_model_moderated, visibility='moderated')

        exp3 = make_experiment(  # noqa: F841
            other_model_moderated, other_model_moderated_version,
            other_protocol_public, other_protocol_public_version,
        )

        # Someone else's moderated model and moderated protocol: should be visible
        exp4 = make_experiment(
            other_model_moderated, other_model_moderated_version,
            other_protocol_moderated, other_protocol_moderated_version,
        )

        # A later public version shouldn't show up
        other_model_second_public_version = helpers.add_fake_version(other_model_moderated, visibility='public')
        exp4_public = make_experiment(
            other_model_moderated, other_model_second_public_version,
            other_protocol_moderated, other_protocol_moderated_version,
        )

        response = client.get('/experiments/matrix')
        data = json.loads(response.content.decode())

        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(exp4.pk),
        }

        # If however I ask for what I can see, I get experiments with later public versions
        response = client.get('/experiments/matrix?subset=all')
        data = json.loads(response.content.decode())

        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(exp1.pk),
            str(exp2.pk),
            str(exp4_public.pk),
        }

    def test_submatrix(self, client, helpers, quick_experiment_version):
        exp = quick_experiment_version.experiment
        other_model = recipes.model.make()
        other_model_version = helpers.add_fake_version(other_model)
        other_protocol = recipes.protocol.make()
        other_protocol_version = helpers.add_fake_version(other_protocol)
        make_experiment(
            other_model, other_model_version,
            other_protocol, other_protocol_version,
        )

        # Throw in a non-existent protocol so we can make sure it gets ignored
        non_existent_pk = 0
        response = client.get(
            '/experiments/matrix',
            {
                'subset': 'all',
                'rowIds[]': [exp.model.pk, non_existent_pk],
                'columnIds[]': [exp.protocol.pk, non_existent_pk],
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        models = data['getMatrix']['rows']
        assert len(models) == 1
        assert str(exp.model_version.sha) in models
        assert models[str(exp.model_version.sha)]['id'] == str(exp.model_version.sha)
        assert models[str(exp.model_version.sha)]['entityId'] == exp.model.pk

        protocols = data['getMatrix']['columns']
        assert len(protocols) == 1
        assert str(exp.protocol_version.sha) in protocols
        assert protocols[str(exp.protocol_version.sha)]['id'] == str(exp.protocol_version.sha)
        assert protocols[str(exp.protocol_version.sha)]['entityId'] == exp.protocol.pk

        experiments = data['getMatrix']['experiments']
        assert len(experiments) == 1
        assert str(exp.pk) in experiments

    def test_submatrix_with_model_versions(self, client, helpers, quick_experiment_version):
        exp = quick_experiment_version.experiment
        v1 = exp.model_version
        v2 = helpers.add_fake_version(exp.model)
        helpers.add_fake_version(exp.model)  # v3, not used

        # Add an experiment with a different model, which shouldn't appear
        other_model = recipes.model.make()
        other_model_version = helpers.add_fake_version(other_model, 'public')
        make_experiment(other_model, other_model_version, exp.protocol, exp.protocol_version)

        response = client.get(
            '/experiments/matrix',
            {
                'subset': 'all',
                'rowIds[]': [exp.model.pk],
                'rowVersions[]': [str(v1.sha), str(v2.sha)],
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert set(data['getMatrix']['rows'].keys()) == {str(v1.sha), str(v2.sha)}
        assert set(data['getMatrix']['experiments'].keys()) == {str(exp.pk)}

    def test_submatrix_with_all_model_versions(self, client, helpers, quick_experiment_version):
        exp = quick_experiment_version.experiment
        v1 = exp.model_version
        v2 = helpers.add_fake_version(exp.model)
        v3 = helpers.add_fake_version(exp.model)

        exp2 = make_experiment(
            exp.model, v2,
            exp.protocol, exp.protocol_version,
        )

        # Add an experiment with a different model, which shouldn't appear
        other_model = recipes.model.make()
        other_model_version = helpers.add_fake_version(other_model, 'public')
        make_experiment(other_model, other_model_version, exp.protocol, exp.protocol_version)

        response = client.get(
            '/experiments/matrix',
            {
                'subset': 'all',
                'rowIds[]': [exp.model.pk],
                'rowVersions[]': '*',
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert set(data['getMatrix']['rows'].keys()) == {str(v1.sha), str(v2.sha), str(v3.sha)}
        assert set(data['getMatrix']['experiments'].keys()) == {str(exp.pk), str(exp2.pk)}

    def test_submatrix_with_too_many_model_ids(self, client, helpers, quick_experiment_version):
        model = recipes.model.make()

        response = client.get(
            '/experiments/matrix',
            {
                'subset': 'all',
                'rowIds[]': [quick_experiment_version.experiment.model.pk, model.pk],
                'rowVersions[]': '*',
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert len(data['notifications']['errors']) == 1

    def test_submatrix_with_protocol_versions(self, client, helpers, quick_experiment_version):
        exp = quick_experiment_version.experiment
        v1 = exp.protocol_version
        v2 = helpers.add_fake_version(exp.protocol)
        helpers.add_fake_version(exp.protocol)  # v3, not used

        exp2 = make_experiment(
            exp.model, exp.model_version,
            exp.protocol, v2,
        )

        # Add an experiment with a different protocol, which shouldn't appear
        other_protocol = recipes.protocol.make()
        other_protocol_version = helpers.add_fake_version(other_protocol, 'public')
        make_experiment(exp.model, exp.model_version,
                        other_protocol, other_protocol_version)

        response = client.get(
            '/experiments/matrix',
            {
                'subset': 'all',
                'columnIds[]': [exp.protocol.pk],
                'columnVersions[]': [str(v1.sha), str(v2.sha)],
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert set(data['getMatrix']['columns'].keys()) == {str(v1.sha), str(v2.sha)}
        assert set(data['getMatrix']['experiments'].keys()) == {str(exp.pk), str(exp2.pk)}

    def test_submatrix_with_all_protocol_versions(self, client, helpers, quick_experiment_version):
        exp = quick_experiment_version.experiment
        v1 = exp.protocol_version
        v2 = helpers.add_fake_version(exp.protocol)
        v3 = helpers.add_fake_version(exp.protocol)

        exp2 = make_experiment(
            exp.model, exp.model_version,
            exp.protocol, v2,
        )

        # Add an experiment with a different protocol, which shouldn't appear
        other_protocol = recipes.protocol.make()
        other_protocol_version = helpers.add_fake_version(other_protocol, 'public')
        make_experiment(exp.model, exp.model_version,
                        other_protocol, other_protocol_version)

        response = client.get(
            '/experiments/matrix',
            {
                'subset': 'all',
                'columnIds[]': [exp.protocol.pk],
                'columnVersions[]': '*',
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert set(data['getMatrix']['columns'].keys()) == {str(v1.sha), str(v2.sha), str(v3.sha)}
        assert set(data['getMatrix']['experiments'].keys()) == {str(exp.pk), str(exp2.pk)}

    def test_submatrix_with_too_many_protocol_ids(self, client, helpers, quick_experiment_version):
        protocol = recipes.protocol.make()

        response = client.get(
            '/experiments/matrix',
            {
                'subset': 'all',
                'columnIds[]': [quick_experiment_version.experiment.protocol.pk, protocol.pk],
                'columnVersions[]': '*',
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert len(data['notifications']['errors']) == 1

    def test_submatrix_with_models_and_protocols_given(self, client, helpers):
        m1, m2 = recipes.model.make(_quantity=2)
        m1v1 = helpers.add_fake_version(m1, 'public')
        m1v2 = helpers.add_fake_version(m1, 'public')
        m2v1 = helpers.add_fake_version(m2, 'public')
        p1, p2 = recipes.protocol.make(_quantity=2)
        p1v1 = helpers.add_fake_version(p1, 'public')
        p1v2 = helpers.add_fake_version(p1, 'public')
        p2v1 = helpers.add_fake_version(p2, 'public')

        exp1 = make_experiment(m1, m1v1, p1, p1v1)
        exp2 = make_experiment(m1, m1v2, p1, p1v2)
        make_experiment(m2, m2v1, p1, p1v1)  # Should not appear
        make_experiment(m2, m2v1, p2, p2v1)  # Should not appear
        make_experiment(m1, m1v1, p2, p2v1)  # Should not appear

        response = client.get(
            '/experiments/matrix',
            {
                'subset': 'all',
                'rowIds[]': [m1.pk],
                'rowVersions[]': '*',
                'columnIds[]': [p1.pk],
                'columnVersions[]': '*',
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data
        assert set(data['getMatrix']['rows'].keys()) == {str(m1v1.sha), str(m1v2.sha)}
        assert set(data['getMatrix']['columns'].keys()) == {str(p1v1.sha), str(p1v2.sha)}
        assert set(data['getMatrix']['experiments'].keys()) == {str(exp1.pk), str(exp2.pk)}

        # Now select only some versions
        response = client.get(
            '/experiments/matrix',
            {
                'subset': 'all',
                'rowIds[]': [m1.pk],
                'rowVersions[]': [str(m1v1.sha)],
                'columnIds[]': [p1.pk],
                'columnVersions[]': [str(p1v1.sha)],
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data
        assert set(data['getMatrix']['rows'].keys()) == {str(m1v1.sha)}
        assert set(data['getMatrix']['columns'].keys()) == {str(p1v1.sha)}
        assert set(data['getMatrix']['experiments'].keys()) == {str(exp1.pk)}

    def test_experiment_without_version_is_ignored(
        self, client, public_model, public_protocol
    ):
        recipes.experiment.make(
            model=public_model,
            model_version=public_model.repocache.latest_version,
            protocol=public_protocol,
            protocol_version=public_protocol.repocache.latest_version,
        )

        response = client.get('/experiments/matrix?subset=all')
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert len(data['getMatrix']['columns']) == 1
        assert len(data['getMatrix']['experiments']) == 0

    def test_old_version_is_hidden(self, client, public_model, experiment_version, helpers):
        # Add a new model version without corresponding experiment
        new_version = helpers.add_version(public_model, filename='file2.txt')

        # We should now see this version in the matrix, but no experiments
        response = client.get('/experiments/matrix?subset=all')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data
        assert str(new_version.sha) in data['getMatrix']['rows']
        assert str(experiment_version.experiment.protocol_version.sha) in data['getMatrix']['columns']
        assert len(data['getMatrix']['experiments']) == 0


@patch('requests.post', side_effect=generate_response())
@pytest.mark.django_db
class TestNewExperimentView:
    def test_submits_experiment(
        self, mock_post,
        client, logged_in_user, model_with_version, protocol_with_version, planned_experiments
    ):
        model = model_with_version
        protocol = protocol_with_version
        model_version = model.repo.latest_commit.sha
        protocol_version = protocol.repo.latest_commit.sha
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

        # Check this has been removed from the list of planned experiments
        assert PlannedExperiment.objects.count() == planned_experiments - 1
        assert PlannedExperiment.objects.filter(
            model=model, model_version=model.repocache.get_version(model_version),
            protocol=protocol, protocol_version=protocol.repocache.get_version(protocol_version)
        ).count() == 0

        # Check a subsequent submit gives the same experiment version back
        response = client.post(
            '/experiments/new',
            {
                'model': model.pk,
                'protocol': protocol.pk,
                'model_version': model_version,
                'protocol_version': protocol_version,
            }
        )

        assert mock_post.call_count == 1
        assert response.status_code == 200
        data = json.loads(response.content.decode())

        assert 'newExperiment' in data
        assert data['newExperiment']['response']
        assert data['newExperiment']['expId'] == version.experiment.id
        assert data['newExperiment']['versionId'] == version.id
        assert data['newExperiment']['expName'] == version.experiment.name

        # Check re-submit also works if there are multiple versions already
        exp_version2 = recipes.experiment_version.make(
            status='SUCCESS',
            experiment=version.experiment,
        )
        response = client.post(
            '/experiments/new',
            {
                'model': model.pk,
                'protocol': protocol.pk,
                'model_version': model_version,
                'protocol_version': protocol_version,
            }
        )

        assert mock_post.call_count == 1
        assert response.status_code == 200
        data = json.loads(response.content.decode())

        assert 'newExperiment' in data
        assert data['newExperiment']['response']
        assert data['newExperiment']['expId'] == exp_version2.experiment.id
        assert data['newExperiment']['versionId'] == exp_version2.id
        assert data['newExperiment']['expName'] == exp_version2.experiment.name

    @pytest.mark.usefixtures('logged_in_user')
    def test_submit_experiment_requires_permissions(self, mock_post, client):
        response = client.post('/experiments/new', {})

        assert response.status_code == 200
        data = json.loads(response.content.decode())

        assert not data['newExperiment']['response']
        assert (
            data['newExperiment']['responseText'] ==
            'You are not allowed to create a new experiment'
        )

    def test_failure_keeps_planned_experiment(
        self, mock_post,
        client, logged_in_user, model_with_version, protocol_with_version, planned_experiments
    ):
        mock_post.side_effect = generate_response('%s an error occurred')

        model = model_with_version
        protocol = protocol_with_version
        model_version = model.repo.latest_commit.sha
        protocol_version = protocol.repo.latest_commit.sha
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
        assert not data['newExperiment']['response']

        version = ExperimentVersion.objects.get()

        assert data['newExperiment']['expId'] == version.experiment.id
        assert data['newExperiment']['versionId'] == version.id
        assert data['newExperiment']['expName'] == version.experiment.name
        assert version.status == ExperimentVersion.STATUS_FAILED

        # Check this hasn't been removed from the list of planned experiments
        assert PlannedExperiment.objects.count() == planned_experiments
        assert PlannedExperiment.objects.filter(
            model=model, model_version=model_version,
            protocol=protocol, protocol_version=protocol_version
        ).count() == 1

    def test_inapplicable_removes_planned_experiment(
        self, mock_post,
        client, logged_in_user, model_with_version, protocol_with_version, planned_experiments
    ):
        mock_post.side_effect = generate_response('%s inapplicable')

        model = model_with_version
        protocol = protocol_with_version
        model_version = model.repo.latest_commit.sha
        protocol_version = protocol.repo.latest_commit.sha
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
        assert not data['newExperiment']['response']

        version = ExperimentVersion.objects.get()

        assert data['newExperiment']['expId'] == version.experiment.id
        assert data['newExperiment']['versionId'] == version.id
        assert data['newExperiment']['expName'] == version.experiment.name

        # Check this has been removed from the list of planned experiments
        assert PlannedExperiment.objects.count() == planned_experiments - 1
        assert PlannedExperiment.objects.filter(
            model=model, model_version=model_version,
            protocol=protocol, protocol_version=protocol_version
        ).count() == 0

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

        assert response.context['version'] == experiment_version
        assertTemplateUsed(response, 'experiments/experimentversion_detail.html')
        assertContains(response, 'Download archive of all files')

    def test_view_experiment_version_logged_in(self, client, logged_in_user, experiment_version):
        add_permission(logged_in_user, 'create_experiment')
        response = client.get(
            ('/experiments/%d/versions/%d' % (experiment_version.experiment.pk,
                                              experiment_version.pk))
        )

        assert response.context['version'] == experiment_version
        assertTemplateUsed(response, 'experiments/experimentversion_detail.html')
        assertContains(response, 'Download archive of all files')
        assertContains(response, 'a id="rerunExperiment"')


@pytest.mark.django_db
class TestExperimentTasks:

    def test_load_page_other_user(self, client):
        response = client.get('/experiments/tasks')
        assert response.status_code == 302

    @pytest.mark.usefixtures('logged_in_user')
    def test_load_page_logged_in_user(self, client):
        response = client.get('/experiments/tasks')
        assert response.status_code == 200

    @pytest.mark.usefixtures('logged_in_user')
    def test_get_queryset_other_user(self, other_user, client, experiment_version):
        experiment_version.author = other_user
        experiment_version.save()
        recipes.running_experiment.make(runnable=experiment_version)
        assert RunningExperiment.objects.count() == 1
        response = client.get('/experiments/tasks')
        assert len(response.context['runningexperiment_list']) == 0

    def test_get_queryset(self, logged_in_user, client, helpers):
        # Create three experiment versions 2 running and 1 completed
        model_1 = recipes.model.make(author=logged_in_user)
        model_1_version = helpers.add_version(model_1, visibility='public')
        protocol_1 = recipes.protocol.make(author=logged_in_user)
        protocol_1_version = helpers.add_version(protocol_1, visibility='public')
        protocol_1_version2 = helpers.add_version(protocol_1, visibility='public')
        protocol_2 = recipes.protocol.make(author=logged_in_user)
        protocol_2_version = helpers.add_version(protocol_2, visibility='public')

        recipes.experiment_version.make(
            status=ExperimentVersion.STATUS_SUCCESS,
            experiment__model=model_1,
            experiment__model_version=model_1.repocache.get_version(model_1_version.sha),
            experiment__protocol=protocol_1,
            experiment__protocol_version=protocol_1.repocache.get_version(protocol_1_version.sha),
            author=logged_in_user,
        )

        exp_version_2 = recipes.experiment_version.make(
            status=ExperimentVersion.STATUS_QUEUED,
            experiment__model=model_1,
            experiment__model_version=model_1.repocache.get_version(model_1_version.sha),
            experiment__protocol=protocol_1,
            experiment__protocol_version=protocol_1.repocache.get_version(protocol_1_version2.sha),
            author=logged_in_user,
        )
        running_exp_version2 = recipes.running_experiment.make(runnable=exp_version_2)

        exp_version_3 = recipes.experiment_version.make(
            status=ExperimentVersion.STATUS_RUNNING,
            experiment__model=model_1,
            experiment__model_version=model_1.repocache.get_version(model_1_version.sha),
            experiment__protocol=protocol_2,
            experiment__protocol_version=protocol_2.repocache.get_version(protocol_2_version.sha),
            author=logged_in_user,
        )
        running_exp_version3 = recipes.running_experiment.make(runnable=exp_version_3)

        assert ExperimentVersion.objects.count() == 3
        assert RunningExperiment.objects.count() == 2

        # Return only running experiment versions
        response = client.get('/experiments/tasks')
        assert set(response.context['runningexperiment_list']) == {running_exp_version2, running_exp_version3}

        # Cancel one of the running versions check the other one is still present
        client.post('/experiments/tasks', {'chkBoxes[]': [running_exp_version2.runnable.id]})
        response = client.get('/experiments/tasks')
        assert set(response.context['runningexperiment_list']) == {running_exp_version3}
        assert RunningExperiment.objects.count() == 1

    @pytest.mark.usefixtures('logged_in_user')
    def test_returns_404_incorrect_owner(self, other_user, client, experiment_version):
        experiment_version.author = other_user
        experiment_version.save()
        running_exp = recipes.running_experiment.make(runnable=experiment_version)
        assert RunningExperiment.objects.count() == 1
        response = client.post('/experiments/tasks', {'chkBoxes[]': [running_exp.runnable.id]})
        assert RunningExperiment.objects.count() == 1
        assert response.status_code == 404


@pytest.mark.django_db
class TestExperimentDeletion:
    def test_owner_can_delete_experiment(
        self, logged_in_user, client, experiment_with_result
    ):
        experiment = experiment_with_result.experiment
        experiment.author = logged_in_user
        experiment.save()
        exp_ver_path = experiment_with_result.abs_path
        assert Experiment.objects.filter(pk=experiment.pk).exists()

        response = client.post('/experiments/%d/delete' % experiment.pk)

        assert response.status_code == 302
        assert response.url == '/experiments/'

        assert not Experiment.objects.filter(pk=experiment.pk).exists()
        assert not exp_ver_path.exists()

    @pytest.mark.usefixtures('logged_in_user')
    def test_non_owner_cannot_delete_experiment(
        self, other_user, client, experiment_with_result
    ):
        experiment = experiment_with_result.experiment
        experiment.author = other_user
        experiment.save()
        exp_ver_path = experiment_with_result.abs_path

        response = client.post('/experiments/%d/delete' % experiment.pk)

        assert response.status_code == 403
        assert Experiment.objects.filter(pk=experiment.pk).exists()
        assert exp_ver_path.exists()

    def test_owner_can_delete_experiment_version(
        self, logged_in_user, client, experiment_with_result
    ):
        experiment = experiment_with_result.experiment
        experiment_with_result.author = logged_in_user
        experiment_with_result.save()
        exp_ver_path = experiment_with_result.abs_path

        response = client.post('/experiments/%d/versions/%d/delete' % (experiment.pk, experiment_with_result.pk))

        assert response.status_code == 302
        assert response.url == '/experiments/%d/versions/' % experiment.pk

        assert not ExperimentVersion.objects.filter(pk=experiment_with_result.pk).exists()
        assert not exp_ver_path.exists()
        assert Experiment.objects.filter(pk=experiment.pk).exists()

    @pytest.mark.usefixtures('logged_in_user')
    def test_non_owner_cannot_delete_experiment_version(
        self, other_user, client, experiment_with_result
    ):
        experiment = experiment_with_result.experiment
        experiment_with_result.author = other_user
        experiment_with_result.save()
        exp_ver_path = experiment_with_result.abs_path

        response = client.post('/experiments/%d/versions/%d/delete' % (experiment.pk, experiment_with_result.pk))

        assert response.status_code == 403
        assert ExperimentVersion.objects.filter(pk=experiment_with_result.pk).exists()
        assert Experiment.objects.filter(pk=experiment.pk).exists()
        assert exp_ver_path.exists()


@pytest.mark.django_db
class TestExperimentComparisonView:
    def test_compare_experiments(self, client, experiment_version, helpers):
        exp = experiment_version.experiment
        protocol = recipes.protocol.make()
        protocol_commit = helpers.add_version(protocol, visibility='public')

        version2 = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
            experiment__protocol=protocol,
            experiment__protocol_version=protocol.repocache.get_version(protocol_commit.sha),
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

        proto = recipes.protocol.make()
        proto_commit = helpers.add_version(proto, visibility='private')
        ver2 = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
            experiment__protocol=proto,
            experiment__protocol_version=proto.repocache.get_version(proto_commit.sha),
        )

        response = client.get(
            ('/experiments/compare/%d/%d' % (ver1.id, ver2.id))
        )

        assert response.status_code == 200
        assert set(response.context['experiment_versions']) == {ver1}

        assert len(response.context['ERROR_MESSAGES']) == 1

    def test_no_visible_experiments(self, client, experiment_version):
        proto = experiment_version.experiment.protocol
        proto.set_version_visibility('latest', 'private')
        experiment_version.experiment.protocol_version.refresh_from_db()
        assert experiment_version.visibility == 'private'

        response = client.get('/experiments/compare/%d' % (experiment_version.id))

        assert response.status_code == 200
        assert len(response.context['experiment_versions']) == 0


@pytest.mark.django_db
class TestExperimentComparisonJsonView:
    def test_compare_experiments(self, client, experiment_version, helpers):
        exp = experiment_version.experiment
        protocol = recipes.protocol.make()
        protocol_commit = helpers.add_version(protocol, visibility='public')
        exp.protocol.repo.tag('v1')
        populate_entity_cache(exp.protocol)

        version2 = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
            experiment__protocol=protocol,
            experiment__protocol_version=protocol.repocache.get_version(protocol_commit.sha),
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
        assert versions[0]['modelVersion'] == exp.model_version.sha
        assert versions[0]['protoName'] == exp.protocol.name
        assert versions[0]['protoVersion'] == 'v1'
        assert versions[0]['name'] == exp.name
        assert versions[0]['runNumber'] == 1

    def test_only_compare_visible_experiments(self, client, experiment_version, helpers):
        ver1 = experiment_version
        exp = ver1.experiment

        proto = recipes.protocol.make()
        proto_commit = helpers.add_version(proto, visibility='private')
        ver2 = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
            experiment__protocol=proto,
            experiment__protocol_version=proto.repocache.get_version(proto_commit.sha),
        )

        response = client.get(
            ('/experiments/compare/%d/%d/info' % (ver1.id, ver2.id))
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        versions = data['getEntityInfos']['entities']
        assert len(versions) == 1
        assert versions[0]['versionId'] == ver1.id

    def test_file_json(self, client, archive_file_path, helpers, experiment_version):
        experiment_version.author.full_name = 'test user'
        experiment_version.author.save()
        experiment_version.mkdir()
        shutil.copyfile(archive_file_path, str(experiment_version.archive_path))
        exp = experiment_version.experiment
        exp.model.set_version_visibility('latest', 'public')
        exp.protocol.set_version_visibility('latest', 'public')

        protocol = recipes.protocol.make()
        protocol_commit = helpers.add_version(protocol, visibility='public')
        version2 = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=exp.model,
            experiment__model_version=exp.model.repocache.get_version(exp.model_version.sha),
            experiment__protocol=protocol,
            experiment__protocol_version=protocol.repocache.get_version(protocol_commit.sha),
        )
        version2.mkdir()
        shutil.copyfile(archive_file_path, str(version2.archive_path))

        response = client.get(
            ('/experiments/compare/%d/%d/info' % (experiment_version.pk, version2.pk))
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
            '/experiments/%d/versions/%d/download/stdout.txt' % (exp.pk, experiment_version.pk)
        )

    def test_empty_experiment_list(self, client, experiment_version):
        response = client.get('/experiments/compare/info')

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert len(data['getEntityInfos']['entities']) == 0


@pytest.mark.django_db
class TestExperimentVersionJsonView:
    def test_experiment_json(self, client, logged_in_user, experiment_version):
        version = experiment_version

        version.author.full_name = 'test user'
        version.author.save()
        version.status = 'SUCCESS'

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
        assert ver['name'] == '{:%Y-%m-%d %H:%M:%S}'.format(version.created_at)
        assert ver['experimentId'] == version.experiment.id
        assert ver['version'] == version.id
        assert ver['files'] == []
        assert ver['numFiles'] == 0
        assert ver['download_url'] == (
            '/experiments/%d/versions/%d/archive' % (version.experiment.pk, version.pk)
        )

    def test_file_json(self, client, archive_file_path, experiment_version):
        version = experiment_version
        version.author.full_name = 'test user'
        version.author.save()
        version.mkdir()
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
        experiment_version.mkdir()
        experiment_version.experiment.model.name = 'my_model'
        experiment_version.experiment.model.save()
        experiment_version.experiment.protocol.name = 'my_protocol'
        experiment_version.experiment.protocol.save()
        shutil.copyfile(archive_file_path, str(experiment_version.archive_path))

        response = client.get(
            '/experiments/%d/versions/%d/archive' %
            (experiment_version.experiment.pk, experiment_version.pk)
        )
        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert set(archive.namelist()) == {
            'stdout.txt', 'errors.txt', 'manifest.xml', 'oxmeta:membrane%3Avoltage - space.csv'}
        assert response['Content-Disposition'] == (
            'attachment; filename=my_model__my_protocol.zip'
        )

    def test_returns_404_if_no_archive_exists(self, client, experiment_version):
        response = client.get(
            '/experiments/%d/versions/%d/archive' %
            (experiment_version.experiment.pk, experiment_version.pk)
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestExperimentFileDownloadView:
    def test_download_file(self, client, archive_file_path, experiment_version):
        experiment_version.mkdir()
        shutil.copyfile(archive_file_path, str(experiment_version.archive_path))

        response = client.get(
            '/experiments/%d/versions/%d/download/stdout.txt' %
            (experiment_version.experiment.pk, experiment_version.pk)
        )
        assert response.status_code == 200
        assert response.content == b'line of output\nmore output\n'
        assert response['Content-Disposition'] == (
            'attachment; filename=stdout.txt'
        )
        assert response['Content-Type'] == 'text/plain'

    def test_handles_odd_characters(self, client, archive_file_path, experiment_version):
        experiment_version.mkdir()
        shutil.copyfile(archive_file_path, str(experiment_version.archive_path))
        filename = 'oxmeta:membrane%3Avoltage - space.csv'

        response = client.get(
            reverse('experiments:file_download',
                    args=[experiment_version.experiment.pk, experiment_version.pk, filename])
        )

        assert response.status_code == 200
        assert response.content == b'1,1\n'
        assert response['Content-Disposition'] == (
            'attachment; filename=' + filename
        )
        assert response['Content-Type'] == 'text/csv'

    def test_disallows_non_local_files(self, client, archive_file_path, experiment_version):
        experiment_version.mkdir()
        shutil.copyfile(archive_file_path, str(experiment_version.archive_path))

        for filename in ['/etc/passwd', '../../../pytest.ini']:
            response = client.get(
                '/experiments/%d/versions/%d/download/%s' % (
                    experiment_version.experiment.pk, experiment_version.pk, filename)
            )
            assert response.status_code == 404


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
        client, logged_in_user, archive_file_path, helpers,
        url
    ):
        model = recipes.model.make(author=logged_in_user)
        model_version = helpers.add_version(model, visibility='private')
        protocol = recipes.protocol.make()
        protocol_version = helpers.add_version(protocol, visibility='public')
        experiment_version = recipes.experiment_version.make(
            experiment__model=model,
            experiment__model_version=model.repocache.get_version(model_version.sha),
            experiment__protocol=protocol,
            experiment__protocol_version=protocol.repocache.get_version(protocol_version.sha),
        )

        experiment_version.mkdir()
        shutil.copyfile(archive_file_path, str(experiment_version.archive_path))

        exp_url = url % (experiment_version.experiment.pk, experiment_version.pk)
        assert client.get(exp_url, follow=True).status_code == 200

    @pytest.mark.usefixtures('logged_in_user')
    def test_private_expt_invisible_to_other_user(self, client, other_user,
                                                  experiment_version, url):
        experiment_version.author = other_user
        experiment_version.save()
        experiment_version.experiment.protocol.set_version_visibility('latest', 'private')

        exp_url = url % (experiment_version.experiment.pk, experiment_version.pk)
        response = client.get(exp_url)
        assert response.status_code == 404

    def test_private_entity_requires_login_for_anonymous(self, client, experiment_version, url):
        experiment_version.experiment.model.set_version_visibility('latest', 'private')

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
