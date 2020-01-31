import io
import json
import os
import uuid
import zipfile
from datetime import timedelta
from io import BytesIO
from subprocess import SubprocessError
from unittest.mock import patch

import pytest
import requests
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.utils.dateparse import parse_datetime
from git import GitCommandError
from guardian.shortcuts import assign_perm

from core import recipes
from entities.models import AnalysisTask, ModelEntity, ProtocolEntity
from experiments.models import Experiment, PlannedExperiment
from repocache.models import ProtocolInterface


@pytest.fixture
def analysis_task(protocol_with_version):
    """A single AnalysisTask instance with associated Protocol version & repocache set up."""
    task = recipes.analysis_task.make(
        entity=protocol_with_version,
        version=protocol_with_version.repocache.latest_version.sha)
    return task


@pytest.mark.django_db
class TestEntityCreation:
    def test_create_model(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        response = client.post('/entities/models/new', data={
            'name': 'mymodel',
            'visibility': 'private',
        })
        assert response.status_code == 302

        assert ModelEntity.objects.count() == 1

        entity = ModelEntity.objects.first()
        assert response.url == '/entities/models/%d/versions/new' % entity.id
        assert entity.name == 'mymodel'
        assert entity.author == logged_in_user

        assert entity.repo_abs_path.exists()

    def test_create_model_requires_permissions(self, logged_in_user, client):
        response = client.post(
            '/entities/models/new',
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_create_protocol(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_protocol')
        response = client.post('/entities/protocols/new', data={
            'name': 'myprotocol',
            'visibility': 'public',
        })
        assert response.status_code == 302

        assert ProtocolEntity.objects.count() == 1

        entity = ProtocolEntity.objects.first()
        assert response.url == '/entities/protocols/%d/versions/new' % entity.id
        assert entity.name == 'myprotocol'
        assert entity.author == logged_in_user

        assert entity.repo_abs_path.exists()

    def test_create_protocol_requires_permissions(self, logged_in_user, client):
        response = client.post(
            '/entities/protocols/new',
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url


@pytest.mark.django_db
@pytest.mark.parametrize("recipe,url,list_url", [
    (recipes.model, '/entities/models/%d/delete', '/entities/models/'),
    (recipes.protocol, '/entities/protocols/%d/delete', '/entities/protocols/'),
])
class TestEntityDeletion:
    def test_owner_can_delete_entity(
        self,
        logged_in_user, client, helpers,      # fixtures
        recipe, url, list_url       # parameters
    ):
        entity = recipe.make(author=logged_in_user)
        repo_path = entity.repo_abs_path
        helpers.add_version(entity)
        assert type(entity).objects.filter(pk=entity.pk).exists()
        assert repo_path.exists()

        response = client.post(url % entity.pk)

        assert response.status_code == 302
        assert response.url == list_url

        assert not type(entity).objects.filter(pk=entity.pk).exists()
        assert not repo_path.exists()

    @pytest.mark.usefixtures('logged_in_user')
    def test_non_owner_cannot_delete_entity(
        self,
        other_user, client, helpers,
        recipe, url, list_url
    ):
        entity = recipe.make(author=other_user)
        repo_path = entity.repo_abs_path
        helpers.add_version(entity)

        response = client.post(url % entity.pk)

        assert response.status_code == 403
        assert type(entity).objects.filter(pk=entity.pk).exists()
        assert repo_path.exists()


@pytest.mark.django_db
class TestEntityDetail:
    def test_redirects_to_new_version(self, client, logged_in_user):
        model = recipes.model.make(author=logged_in_user)
        response = client.get('/entities/models/%d' % model.pk)
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/new' % model.pk

    def test_redirects_to_latest_version(self, client, logged_in_user, helpers):
        model = recipes.model.make()
        helpers.add_version(model, visibility='public')
        response = client.get('/entities/models/%d' % model.pk)
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/latest' % model.pk


@pytest.mark.django_db
class TestEntityVersionView:
    def check(self, client, url, version, tags):
        response = client.get(url)
        assert response.status_code == 200
        assert response.context['version'] == version
        assert set(response.context['tags']) == set(tags)

    def test_view_entity_version(self, client, logged_in_user, helpers):
        model = recipes.model.make()
        helpers.add_version(model, visibility='public')
        commit = model.repo.latest_commit
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, commit.sha),
                   commit, [])
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   commit, [])

        # Now add a second version with tag
        assert len(list(model.repo.commits)) == 1
        commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('my_tag', commit2.sha)

        # Commits are yielded newest first
        assert len(list(model.repo.commits)) == 2
        assert commit == list(model.repo.commits)[-1]
        commit = model.repo.latest_commit

        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, commit.sha),
                   commit, ['my_tag'])
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, 'my_tag'),
                   commit, ['my_tag'])
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   commit, ['my_tag'])

    def test_version_with_two_tags(self, client, helpers):
        model = recipes.model.make()
        helpers.add_version(model, visibility='public')
        commit = model.repo.latest_commit
        model.add_tag('tag1', commit.sha)
        model.add_tag('tag2', commit.sha)
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, commit.sha),
                   commit, ['tag1', 'tag2'])
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, 'tag1'),
                   commit, ['tag1', 'tag2'])
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, 'tag2'),
                   commit, ['tag1', 'tag2'])
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   commit, ['tag1', 'tag2'])

    def test_shows_correct_visibility(self, client, logged_in_user, model_with_version):
        model = model_with_version
        commit = model.repo.latest_commit
        model.set_version_visibility(commit.sha, 'public')

        response = client.get(
            '/entities/models/%d/versions/%s' % (model.pk, commit.sha),
        )

        assert response.status_code == 200
        assert response.context['visibility'] == 'public'
        assert response.context['form'].initial.get('visibility') == 'public'

    def test_cannot_access_invisible_version(self, client, logged_in_user, helpers):
        model = recipes.model.make()
        commit1 = helpers.add_version(model, visibility='private')
        helpers.add_version(model, visibility='public')
        model.add_tag('tag1', commit1.sha)

        response = client.get('/entities/models/%d/versions/%s' % (model.pk, commit1.sha))
        assert response.status_code == 404

        response = client.get('/entities/models/%d/versions/%s' % (model.pk, 'tag1'))
        assert response.status_code == 404

    def test_anonymous_cannot_access_invisible_version(self, client, helpers):
        model = recipes.model.make()
        commit1 = helpers.add_version(model, visibility='private')
        helpers.add_version(model, visibility='public')
        model.add_tag('tag1', commit1.sha)

        response = client.get('/entities/models/%d/versions/%s' % (model.pk, commit1.sha))
        assert response.status_code == 302

        response = client.get('/entities/models/%d/versions/%s' % (model.pk, 'tag1'))
        assert response.status_code == 302

    def test_no_token_access(self, client, queued_experiment):
        model = queued_experiment.experiment.model
        sha = model.repo.latest_commit.sha
        queued_experiment.experiment.model.set_version_visibility(sha, 'private')

        response = client.get(
            '/entities/models/%d/versions/%s' % (model.pk, sha),
            HTTP_AUTHORIZATION='Token {}'.format(queued_experiment.signature)
        )

        assert response.status_code == 302

    def test_404_for_version_not_in_cache(self, client, helpers):
        model = recipes.model.make()
        commit = helpers.add_version(model, visibility='public', cache=False)

        response = client.get(
            '/entities/models/%d/versions/%s' % (model.pk, commit.sha)
        )
        assert response.status_code == 404

    def test_404_for_version_not_in_repo(self, client, helpers):
        model = recipes.model.make()
        recipes.cached_model_version.make(
            entity__entity=model,
            sha='test-sha',
            visibility='public'
        )

        response = client.get(
            '/entities/models/%d/versions/%s' % (model.pk, 'test-sha')
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestEntityVersionChangeVisibilityView:
    def test_change_visibility(self, client, logged_in_user, helpers):
        helpers.login(client, logged_in_user)
        model = recipes.model.make(author=logged_in_user)
        commit = helpers.add_version(model)
        assert model.get_version_visibility(commit.sha) == 'private'

        response = client.post(
            '/entities/models/%d/versions/%s/visibility' % (model.pk, commit.sha),
            data={
                'visibility': 'public',
            })

        assert response.status_code == 200
        assert model.get_version_visibility(commit.sha) == 'public'
        assert model.repocache.get_version(commit.sha).visibility == 'public'

    def test_non_owner_cannot_change_visibility(self, client, logged_in_user, other_user, helpers):
        helpers.login(client, logged_in_user)
        model = recipes.model.make(author=other_user)
        commit = helpers.add_version(model)

        response = client.post(
            '/entities/models/%d/versions/%s/visibility' % (model.pk, commit.sha),
            data={
                'visibility': 'public',
            })

        assert response.status_code == 403
        assert model.get_version_visibility(commit.sha) != 'public'


@pytest.mark.django_db
class TestEntityVersionJsonView:
    @pytest.mark.parametrize("can_create_expt,is_parsed_ok", [(True, True), (False, False)])
    def test_version_json(self, client, logged_in_user, helpers, can_create_expt, is_parsed_ok):
        if can_create_expt:
            helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(name='mymodel', author__full_name='model author')
        version = helpers.add_version(model)
        model.set_version_visibility(version.sha, 'public')
        model.repo.tag('v1')
        planned_expt = PlannedExperiment(
            submitter=logged_in_user,
            model=model, model_version=version.sha,
            protocol=recipes.protocol.make(), protocol_version=uuid.uuid4(),
        )
        planned_expt.save()
        cached_version = model.repocache.get_version(version.sha)
        cached_version.parsed_ok = is_parsed_ok
        cached_version.save()

        response = client.get('/entities/models/%d/versions/latest/files.json' % model.pk)

        assert response.status_code == 200

        data = json.loads(response.content.decode())
        ver = data['version']

        assert ver['name'] == 'mymodel'
        assert ver['id'] == version.sha
        assert ver['author'] == 'author'  # Commit author not entity author
        assert ver['entityId'] == model.pk
        assert ver['visibility'] == 'public'
        assert (
            parse_datetime(ver['created']).replace(microsecond=0) ==
            version.timestamp
        )
        assert ver['version'] == 'v1'
        assert ver['parsedOk'] == is_parsed_ok
        assert len(ver['files']) == ver['numFiles'] == 1
        assert ver['url'] == '/entities/models/%d/versions/%s' % (model.pk, version.sha)
        assert (ver['download_url'] ==
                '/entities/models/%d/versions/%s/archive' % (model.pk, version.sha))
        assert 'change_url' in ver

        file_ = ver['files'][0]
        assert file_['id'] == file_['name'] == 'file1.txt'
        assert file_['filetype'] == 'TXTPROTOCOL'
        assert file_['size'] == 15
        assert (file_['url'] ==
                '/entities/models/%d/versions/%s/download/file1.txt' % (model.pk, version.sha))

        if can_create_expt:
            assert len(ver['planned_experiments']) == 1
            planned = ver['planned_experiments'][0]
            assert planned['model'] == model.pk
            assert planned['model_version'] == version.sha
            assert planned['protocol'] == planned_expt.protocol.pk
            assert planned['protocol_version'] == str(planned_expt.protocol_version)
        else:
            assert len(ver['planned_experiments']) == 0


@pytest.mark.django_db
class TestGetProtocolInterfacesJsonView:
    def add_version_with_interface(self, helpers, protocol, req, opt, vis='public'):
        """Helper method to add a new version and give it an interface in one go."""
        version = helpers.add_fake_version(protocol, vis)
        # Give it an interface
        terms = [
            ProtocolInterface(protocol_version=version, term=t, optional=False) for t in req
        ] + [
            ProtocolInterface(protocol_version=version, term=t, optional=True) for t in opt
        ]
        ProtocolInterface.objects.bulk_create(terms)

    def test_single_public_protocol(self, client, helpers):
        # Make a public protocol version
        protocol = recipes.protocol.make()
        req = ['r1', 'r2']
        opt = ['o1']
        self.add_version_with_interface(helpers, protocol, req, opt)

        response = client.get('/entities/protocols/get_interfaces')

        assert response.status_code == 200

        data = json.loads(response.content.decode())
        interfaces = data['interfaces']

        assert len(interfaces) == 1
        iface = interfaces[0]
        assert iface['name'] == protocol.name
        assert set(iface['required']) == set(req)
        assert set(iface['optional']) == set(opt)

    def test_complex_visibilities(self, client, logged_in_user, other_user, helpers):
        # Models shouldn't appear at all
        model1 = recipes.model.make()
        helpers.add_fake_version(model1, 'public')
        model2 = recipes.model.make(author=logged_in_user)
        helpers.add_fake_version(model2, 'private')
        model3 = recipes.model.make(author=other_user)
        helpers.add_fake_version(model3, 'public')
        helpers.add_fake_version(model3, 'private')
        # One public protocol with 2 versions, each with a different interface
        protocol1 = recipes.protocol.make()
        self.add_version_with_interface(helpers, protocol1, ['p1r1'], ['p1o1'], vis='public')
        self.add_version_with_interface(helpers, protocol1, ['p1r2'], ['p1o2'], vis='public')

        # A private protocol owned by logged_in_user, with 2 versions, each with a different interface
        protocol2 = recipes.protocol.make(author=logged_in_user)
        self.add_version_with_interface(helpers, protocol2, ['p2r1'], ['p2o1'], vis='private')
        self.add_version_with_interface(helpers, protocol2, ['p2r2'], ['p2o2'], vis='private')

        # A private protocol owned by other_user, with 2 versions, each with a different interface, first one public
        protocol3 = recipes.protocol.make(author=other_user)
        self.add_version_with_interface(helpers, protocol3, ['p3r1'], ['p3o1'], vis='public')
        self.add_version_with_interface(helpers, protocol3, ['p3r2'], ['p3o2'], vis='private')

        # A private protocol owned by other_user but shared with logged_in_user,
        # with 3 versions, each with a different interface, middle one public
        protocol4 = recipes.protocol.make(author=other_user)
        assign_perm('edit_entity', logged_in_user, protocol4)
        self.add_version_with_interface(helpers, protocol4, ['p4r1'], ['p4o1'], vis='private')
        self.add_version_with_interface(helpers, protocol4, ['p4r2'], ['p4o2'], vis='public')
        self.add_version_with_interface(helpers, protocol4, ['p4r3'], ['p4o3'], vis='private')

        # Get all interfaces visible to logged_in_user
        response = client.get('/entities/protocols/get_interfaces')
        assert response.status_code == 200
        interfaces = json.loads(response.content.decode())['interfaces']
        assert len(interfaces) == 4

        expected = {
            'myprotocol1': {'required': ['p1r2'], 'optional': ['p1o2']},
            'myprotocol2': {'required': ['p2r2'], 'optional': ['p2o2']},
            'myprotocol3': {'required': ['p3r1'], 'optional': ['p3o1']},
            'myprotocol4': {'required': ['p4r3'], 'optional': ['p4o3']},
        }
        for iface in interfaces:
            assert iface['name'] in expected
            assert iface['required'] == expected[iface['name']]['required']
            assert iface['optional'] == expected[iface['name']]['optional']


@pytest.mark.django_db
class TestModelEntityCompareExperimentsView:
    def test_shows_related_experiments(self, client, helpers, experiment_version):
        exp = experiment_version.experiment
        sha = exp.model.repo.latest_commit.sha
        recipes.experiment_version.make()  # another experiment which should not be included
        exp.model.set_version_visibility('latest', 'public')
        exp.protocol.set_version_visibility('latest', 'public')

        # Add an experiment with a newer version of the protocol but that was created earlier
        exp2 = recipes.experiment_version.make(
            experiment__protocol=exp.protocol,
            experiment__protocol_version=helpers.add_version(exp.protocol, visibility='public').sha,
            experiment__model=exp.model,
            experiment__model_version=sha,
        ).experiment
        exp2.created_at = exp.created_at - timedelta(seconds=10)
        exp2.save()

        # Add an experiment with a newer version of the protocol and that was created later
        exp3 = recipes.experiment_version.make(
            experiment__protocol=exp.protocol,
            experiment__protocol_version=helpers.add_version(exp.protocol, visibility='public').sha,
            experiment__model=exp.model,
            experiment__model_version=sha,
        ).experiment

        response = client.get(
            '/entities/models/%d/versions/%s/compare' % (exp.model.pk, sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [(exp.protocol, [exp3, exp2, exp])]

    def test_applies_visibility(self, client, helpers, experiment_version):
        exp = experiment_version.experiment
        sha = exp.model_version
        protocol = recipes.protocol.make()
        exp.model.set_version_visibility('latest', 'public')
        exp.protocol.set_version_visibility('latest', 'public')

        recipes.experiment_version.make(
            experiment__protocol=protocol,
            experiment__protocol_version=helpers.add_version(protocol, visibility='private').sha,
            experiment__model=exp.model,
            experiment__model_version=sha,
        )  # should not be included for visibility reasons

        response = client.get(
            '/entities/models/%d/versions/%s/compare' % (exp.model.pk, sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [(exp.protocol, [exp])]

    def test_returns_404_if_commit_not_found(self, client, logged_in_user):
        model = recipes.model.make()

        response = client.get(
            '/entities/models/%d/versions/%s/compare' % (model.pk, 'nocommit')
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestProtocolEntityCompareExperimentsView:
    def test_shows_related_experiments(self, client, logged_in_user, experiment_version):
        exp = experiment_version.experiment
        exp.protocol.set_version_visibility('latest', 'public')
        exp.author = logged_in_user
        exp.save()

        sha = exp.protocol.repo.latest_commit.sha
        recipes.experiment_version.make(
            experiment__author=logged_in_user
        ).experiment  # should not be included, as it uses a different protocol

        response = client.get(
            '/entities/protocols/%d/versions/%s/compare' % (exp.protocol.pk, sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [(exp.model, [exp])]

    def test_applies_visibility(self, client, helpers, experiment_version):
        exp = experiment_version.experiment
        sha = exp.protocol_version
        model = recipes.model.make()
        exp.protocol.set_version_visibility('latest', 'public')
        exp.model.set_version_visibility('latest', 'public')

        recipes.experiment_version.make(
            experiment__protocol=exp.protocol,
            experiment__protocol_version=sha,
            experiment__model=model,
            experiment__model_version=helpers.add_version(model, visibility='private').sha,
        )  # should not be included for visibility reasons

        response = client.get(
            '/entities/protocols/%d/versions/%s/compare' % (exp.protocol.pk, sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [(exp.model, [exp])]

    def test_returns_404_if_commit_not_found(self, client, logged_in_user):
        protocol = recipes.protocol.make(author=logged_in_user)

        response = client.get(
            '/entities/protocols/%d/versions/%s/compare' % (protocol.pk, 'nocommit')
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestEntityComparisonView:
    def test_loads_entity_versions(self, client, helpers, logged_in_user):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        version_spec = '%d:%s' % (model.pk, v1.sha)
        response = client.get(
            '/entities/models/compare/%s' % version_spec
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == [version_spec]

    def test_cannot_compare_entities_with_no_access(self, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        v2 = helpers.add_version(model, visibility='private')

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)
        response = client.get(
            '/entities/models/compare/%s/%s' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == [v1_spec]

    def test_can_compare_entities_if_collaborator(self, client, logged_in_user, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        v2 = helpers.add_version(model, visibility='private')
        assign_perm('edit_entity', logged_in_user, model)

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)
        response = client.get(
            '/entities/models/compare/%s/%s' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == [v1_spec, v2_spec]

    def test_ignores_invalid_versions(self, client, helpers, logged_in_user):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        version_spec = '%d:%s' % (model.pk, v1.sha)
        response = client.get(
            '/entities/models/compare/%s/%d:nocommit' % (version_spec, model.pk)
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == [version_spec]

    def test_no_valid_versions(self, client, logged_in_user):
        model = recipes.model.make()
        response = client.get(
            '/entities/models/compare/%d:nocommit/%d:nocommit' % (model.pk + 1, model.pk)
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == []


@pytest.mark.django_db
class TestEntityComparisonJsonView:
    def test_compare_entities(self, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        v2 = helpers.add_version(model)

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)
        response = client.get(
            '/entities/models/compare/%s/%s/info' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        versions = data['getEntityInfos']['entities']
        assert versions[0]['id'] == v1.sha
        assert versions[1]['id'] == v2.sha
        assert versions[0]['author'] == v1.author.name
        assert versions[0]['visibility'] == 'public'
        assert versions[0]['name'] == model.name
        assert versions[0]['version'] == v1.sha
        assert versions[0]['numFiles'] == 1
        assert versions[0]['commitMessage'] == v1.message
        assert versions[0]['url'] == '/entities/models/%d/versions/%s' % (model.pk, v1.sha)

    def test_cannot_compare_entities_with_no_access(self, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        v2 = helpers.add_version(model, visibility='private')

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)
        response = client.get(
            '/entities/models/compare/%s/%s/info' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        versions = data['getEntityInfos']['entities']
        assert len(versions) == 1
        assert versions[0]['id'] == v1.sha

    def test_can_compare_entities_if_collaborator(self, client, logged_in_user, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        v2 = helpers.add_version(model, visibility='private')
        assign_perm('edit_entity', logged_in_user, model)

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)
        response = client.get(
            '/entities/models/compare/%s/%s/info' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        versions = data['getEntityInfos']['entities']
        assert len(versions) == 2
        assert versions[0]['id'] == v1.sha
        assert versions[1]['id'] == v2.sha

    def test_file_json(self, client, helpers):
        model = recipes.model.make()
        filename = 'oxmeta:v%3A.txt'
        v1 = helpers.add_version(model, visibility='public', filename=filename)

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        response = client.get(
            '/entities/models/compare/%s/info' % v1_spec
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        versions = data['getEntityInfos']['entities']
        assert versions[0]['id'] == v1.sha
        assert versions[0]['numFiles'] == 1
        file_ = versions[0]['files'][0]
        assert file_['id'] == filename
        assert file_['name'] == filename
        assert file_['author'] == v1.author.name
        assert file_['filetype'] == 'TXTPROTOCOL'
        assert file_['size'] == 15
        assert file_['url'] == (
            '/entities/models/%d/versions/%s/download/%s' % (model.pk, v1.sha, filename.replace('%', '%25')))

    def test_ignores_invalid_versions(self, client, logged_in_user, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        version_spec = '%d:%s' % (model.pk, v1.sha)
        response = client.get(
            '/entities/models/compare/%s/%d:nocommit' % (version_spec, model.pk)
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == [version_spec]

    def test_no_valid_versions(self, client, logged_in_user):
        model = recipes.model.make()
        response = client.get(
            '/entities/models/compare/%d:nocommit/%d:nocommit' % (model.pk + 1, model.pk)
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == []


@pytest.mark.django_db
class TestTagging:
    def test_tag_specific_ref(self, helpers):
        model = recipes.model.make()
        commit = helpers.add_version(model)
        helpers.add_version(model)
        model.repo.tag('tag', ref=commit.sha)
        tags = model.repo.tag_dict
        assert len(tags) == 1
        assert tags[commit.sha][0].name == 'tag'

    def test_nasty_tag_chars(self, helpers):
        model = recipes.model.make()
        helpers.add_version(model)

        with pytest.raises(GitCommandError):
            model.repo.tag('tag/')

        model.repo.tag('my/tag')
        assert model.repo.tag_dict[model.repo.latest_commit.sha][0].name == 'my/tag'

        with pytest.raises(GitCommandError):
            model.repo.tag('tag with spaces')

    def test_cant_use_same_tag_twice(self, helpers):
        model = recipes.model.make()
        helpers.add_version(model)
        model.repo.tag('tag')
        helpers.add_version(model)
        with pytest.raises(GitCommandError):
            model.repo.tag('tag')

    def test_user_can_add_tag(self, logged_in_user, client, helpers):
        model = recipes.model.make(author=logged_in_user)
        helpers.add_permission(logged_in_user, 'create_model')
        helpers.add_version(model)
        commit = model.repo.latest_commit

        response = client.post(
            '/entities/tag/%d/%s' % (model.pk, commit.sha),
            data={
                'tag': 'v1',
            },
        )
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/%s' % (model.pk, commit.sha)
        assert 'v1' in model.repo._repo.tags
        tags = model.repo.tag_dict
        assert len(tags) == 1
        assert tags[commit.sha][0].name == 'v1'

    def test_cannot_tag_as_non_owner(self, logged_in_user, client, helpers):
        protocol = recipes.protocol.make()
        commit = helpers.add_version(protocol)
        response = client.post(
            '/entities/tag/%d/%s' % (protocol.pk, commit.sha),
            data={},
        )
        assert response.status_code == 302

    def test_can_tag_as_non_owner_with_permissions(self, logged_in_user, client, helpers):
        protocol = recipes.protocol.make()
        commit = helpers.add_version(protocol)
        helpers.add_permission(logged_in_user, 'create_protocol')
        assign_perm('edit_entity', logged_in_user, protocol)
        response = client.post(
            '/entities/tag/%d/%s' % (protocol.pk, commit.sha),
            data={
                'tag': 'v1',
            },
        )
        assert response.status_code == 302
        assert 'v1' in protocol.repo._repo.tags


@pytest.mark.django_db
class TestEntityVersionList:
    def test_view_entity_version_list(self, client, helpers):
        model = recipes.model.make()
        commit1 = helpers.add_version(model, visibility='public')
        commit2 = helpers.add_version(model, visibility='moderated')
        model.add_tag('v1', commit2.sha)

        response = client.get('/entities/models/%d/versions/' % model.pk)
        assert response.status_code == 200
        assert response.context['versions'] == [
            (['v1'], commit2),
            ([], commit1),
        ]

    def test_only_shows_visible_versions(self, client, helpers):
        model = recipes.model.make()
        helpers.add_version(model, visibility='private')
        commit2 = helpers.add_version(model, visibility='public')
        helpers.add_version(model, visibility='private')

        response = client.get('/entities/models/%d/versions/' % model.pk)
        assert response.status_code == 200
        assert response.context['versions'] == [
            ([], commit2),
        ]


@pytest.mark.django_db
class TestEntityList:
    def test_lists_my_models(self, client, logged_in_user):
        models = recipes.model.make(_quantity=2, author=logged_in_user)
        response = client.get('/entities/models/')
        assert response.status_code == 200
        assert list(response.context['object_list']) == models

    def test_lists_my_protocols(self, client, logged_in_user):
        protocols = recipes.protocol.make(_quantity=2, author=logged_in_user)
        response = client.get('/entities/protocols/')
        assert response.status_code == 200
        assert list(response.context['object_list']) == protocols


@pytest.mark.django_db
class TestVersionCreation:
    def test_new_version_form_includes_latest_version(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        commit = helpers.add_version(model, visibility='public')
        response = client.get('/entities/models/%d/versions/new' % model.pk)
        assert response.status_code == 200
        assert response.context['latest_version'] == commit
        assert b'option value="public" selected' in response.content

    def test_no_latest_version(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        response = client.get('/entities/models/%d/versions/new' % model.pk)
        assert response.status_code == 200
        assert response.context['latest_version'] is None
        assert b'option value="private" selected' in response.content

    def test_add_multiple_files(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        recipes.model_file.make(
            entity=model,
            upload=SimpleUploadedFile('file1.txt', b'file 1 wrong'),
            original_name='file1.txt',
        )
        recipes.model_file.make(
            entity=model,
            upload=SimpleUploadedFile('file2.txt', b'file 2'),
            original_name='file2.txt',
        )
        recipes.model_file.make(
            entity=model,
            upload=SimpleUploadedFile('file1_fixed.txt', b'file 1'),
            original_name='file1.txt',
        )

        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'filename[]': ['uploads/file1.txt', 'uploads/file2.txt', 'uploads/file1_fixed.txt'],
                'delete_filename[]': ['file1.txt'],
                'mainEntry': ['file1.txt'],
                'commit_message': 'files',
                'tag': 'v1',
                'visibility': 'public',
            },
        )
        assert response.status_code == 302
        latest = model.repo.latest_commit
        assert response.url == '/entities/models/%d/versions/%s' % (model.id, latest.sha)
        assert 'v1' in model.repo._repo.tags

        assert latest.message == 'files'
        assert 'file1.txt' in latest.filenames
        assert 'file2.txt' in latest.filenames
        assert latest.master_filename == 'file1.txt'

        assert 0 == PlannedExperiment.objects.count()
        assert 0 == model.files.count()

    def test_delete_file(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        helpers.add_version(model, 'file1.txt')
        helpers.add_version(model, 'file2.txt')
        assert len(list(model.repo.latest_commit.files)) == 2

        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'delete_filename[]': ['file1.txt'],
                'commit_message': 'delete file1',
                'tag': 'delete-file',
                'visibility': 'public',
            },
        )
        assert response.status_code == 302
        latest = model.repo.latest_commit
        assert response.url == '/entities/models/%d/versions/%s' % (model.id, latest.sha)
        assert 'delete-file' in model.repo._repo.tags

        assert latest.message == 'delete file1'
        assert len(list(latest.files)) == 2
        assert 'file2.txt' in latest.filenames
        assert not (model.repo_abs_path / 'file1.txt').exists()

        assert 0 == PlannedExperiment.objects.count()
        assert 0 == model.files.count()

    def test_delete_multiple_files(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        helpers.add_version(model, 'file1.txt')
        helpers.add_version(model, 'file2.txt')
        helpers.add_version(model, 'file3.txt')
        assert len(list(model.repo.latest_commit.files)) == 3

        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'delete_filename[]': ['file1.txt', 'file2.txt'],
                'commit_message': 'delete files',
                'tag': 'delete-files',
                'visibility': 'public',
            },
        )
        assert response.status_code == 302
        latest = model.repo.latest_commit
        assert response.url == '/entities/models/%d/versions/%s' % (model.id, latest.sha)
        assert 'delete-files' in model.repo._repo.tags

        assert latest.message == 'delete files'
        assert len(list(latest.files)) == 2
        assert 'file3.txt' in latest.filenames
        assert not (model.repo_abs_path / 'file1.txt').exists()
        assert not (model.repo_abs_path / 'file2.txt').exists()

        assert 0 == PlannedExperiment.objects.count()
        assert 0 == model.files.count()

    def test_replace_file(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        helpers.add_version(model, 'file1.txt')
        helpers.add_version(model, 'file2.txt')
        assert len(list(model.repo.latest_commit.files)) == 2

        # The user changes their mind twice about a new version of file1...
        recipes.model_file.make(
            entity=model,
            upload=SimpleUploadedFile('file1_v2.txt', b'file 1 wrong'),
            original_name='file1.txt',
        )
        recipes.model_file.make(
            entity=model,
            upload=SimpleUploadedFile('file1_v3.txt', b'file 1 new'),
            original_name='file1.txt',
        )

        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'filename[]': ['uploads/file1_v2.txt', 'uploads/file1_v3.txt'],
                'delete_filename[]': ['file1.txt', 'file1.txt'],
                'commit_message': 'replace file1',
                'tag': 'replace-file',
                'visibility': 'public',
            },
        )
        assert response.status_code == 302
        latest = model.repo.latest_commit
        assert response.url == '/entities/models/%d/versions/%s' % (model.id, latest.sha)
        assert 'replace-file' in model.repo._repo.tags

        assert latest.message == 'replace file1'
        assert len(list(latest.files)) == 3
        assert {'manifest.xml', 'file1.txt', 'file2.txt'} == latest.filenames
        with (model.repo_abs_path / 'file1.txt').open() as f:
            assert f.read() == 'file 1 new'

        assert 0 == PlannedExperiment.objects.count()
        assert 0 == model.files.count()

    def test_delete_nonexistent_file(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        helpers.add_version(model, 'file1.txt')

        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'delete_filename[]': ['file2.txt'],
                'commit_message': 'delete file2',
                'version': 'delete-file',
                'visibility': 'public',
            },
        )
        assert response.status_code == 200
        assert 'delete-file' not in model.repo._repo.tags
        assert model.repo.latest_commit.message != 'delete file2'
        assert 0 == model.files.count()

    def test_create_model_version(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model_file.make(
            entity__author=logged_in_user,
            upload=SimpleUploadedFile('model.txt', b'my test model'),
            original_name='model.txt',
        ).entity
        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'filename[]': 'uploads/model.txt',
                'commit_message': 'first commit',
                'tag': 'v1',
                'visibility': 'public',
            },
        )
        assert response.status_code == 302
        commit = model.repo.latest_commit
        assert response.url == '/entities/models/%d/versions/%s' % (model.id, commit.sha)

        assert 0 == PlannedExperiment.objects.count()
        assert 0 == model.files.count()

    def test_cannot_create_model_version_as_non_owner(self, logged_in_user, client):
        model = recipes.model.make()
        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url

    @patch('entities.processing.submit_check_protocol_task')
    def test_create_protocol_version(self, mock_check, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_protocol')
        doc = b'\n# Title\n\ndocumentation goes here\nand here'
        content = b'my test protocol\ndocumentation\n{' + doc + b'}'
        protocol = recipes.protocol_file.make(
            entity__author=logged_in_user,
            upload=SimpleUploadedFile('protocol.txt', content),
            original_name='protocol.txt',
        ).entity
        response = client.post(
            '/entities/protocols/%d/versions/new' % protocol.pk,
            data={
                'filename[]': 'uploads/protocol.txt',
                'mainEntry': ['protocol.txt'],
                'commit_message': 'first commit',
                'tag': 'v1',
                'visibility': 'public',
            },
        )
        assert response.status_code == 302
        commit = protocol.repo.latest_commit
        assert response.url == '/entities/protocols/%d/versions/%s' % (protocol.id, commit.sha)
        # Check documentation parsing
        assert ProtocolEntity.README_NAME in commit.filenames
        readme = commit.get_blob(ProtocolEntity.README_NAME)
        assert readme.data_stream.read() == doc
        # Check new version analysis "happened"
        assert mock_check.called
        mock_check.assert_called_once_with(protocol, commit.sha)

        assert 0 == PlannedExperiment.objects.count()
        assert 0 == protocol.files.count()

    @patch('requests.post', side_effect=requests.exceptions.ConnectionError)
    def test_protocol_analysis_errors(self, mock_post, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_protocol')
        doc = b'\n# Title\n\ndocumentation goes here\nand here'
        content = b'my test protocol\ndocumentation\n{' + doc + b'}'
        protocol = recipes.protocol_file.make(
            entity__author=logged_in_user,
            upload=SimpleUploadedFile('protocol.txt', content),
            original_name='protocol.txt',
        ).entity
        response = client.post(
            '/entities/protocols/%d/versions/new' % protocol.pk,
            data={
                'filename[]': 'uploads/protocol.txt',
                'mainEntry': ['protocol.txt'],
                'commit_message': 'first commit',
                'tag': 'v1',
                'visibility': 'public',
            },
        )
        assert response.status_code == 302
        commit = protocol.repo.latest_commit
        assert response.url == '/entities/protocols/%d/versions/%s' % (protocol.id, commit.sha)
        # Check documentation parsing
        assert ProtocolEntity.README_NAME in commit.filenames
        readme = commit.get_blob(ProtocolEntity.README_NAME)
        assert readme.data_stream.read() == doc
        # Check new version analysis "happened" but failed cleanly
        assert mock_post.called
        assert not AnalysisTask.objects.exists()

        # If instead the backend returns an error...
        mock_post.side_effect = None
        mock_post.return_value.content = b'error'
        # ...then we should also get a clean failure
        from entities.processing import submit_check_protocol_task
        submit_check_protocol_task(protocol, commit.sha)
        assert mock_post.called
        assert not AnalysisTask.objects.exists()

    def test_cannot_create_protocol_version_as_non_owner(self, logged_in_user, client):
        protocol = recipes.protocol.make()
        response = client.post(
            '/entities/protocols/%d/versions/new' % protocol.pk,
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_rolls_back_if_tag_exists(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        first_commit = helpers.add_version(model, tag_name='v1')

        recipes.model_file.make(
            entity=model,
            upload=SimpleUploadedFile('model.txt', b'my test model'),
            original_name='model.txt',
        )
        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'filename[]': 'uploads/model.txt',
                'commit_message': 'first commit',
                'tag': 'v1',
                'visibility': 'public',
            },
        )
        assert response.status_code == 200
        assert model.repo.latest_commit == first_commit
        assert not (model.repo_abs_path / 'model.txt').exists()

    @pytest.mark.parametrize("route", ['main_form', 'edit_file'])
    def test_rerun_experiments(self, logged_in_user, other_user, client, helpers, route):
        # Set up previous experiments
        model = recipes.model.make(author=logged_in_user)
        model_first_commit = helpers.add_version(model, visibility='private')
        model_commit = helpers.add_version(model, visibility='private')
        other_model = recipes.model.make(author=other_user)
        other_model_commit = helpers.add_version(other_model, visibility='public')

        def _add_experiment(proto_author, proto_vis, shared=False,
                            proto=None, proto_commit=None,
                            model=model, model_commit=model_commit):
            if proto is None:
                proto = recipes.protocol.make(author=proto_author)
                proto_commit = helpers.add_version(proto, visibility=proto_vis)
            recipes.experiment_version.make(
                status='SUCCESS',
                experiment__model=model,
                experiment__model_version=model_commit.sha,
                experiment__protocol=proto,
                experiment__protocol_version=proto_commit.sha,
            )
            if shared:
                assign_perm('edit_entity', logged_in_user, proto)
            return proto

        my_private_protocol = _add_experiment(logged_in_user, 'private')  # Re-run case 1
        _add_experiment(logged_in_user, 'private',  # Shouldn't be re-run
                        model=model, model_commit=model_first_commit)
        _add_experiment(logged_in_user, 'private',  # Does get re-run because same proto version as case 1
                        proto=my_private_protocol, proto_commit=my_private_protocol.repo.latest_commit,
                        model=model, model_commit=model_first_commit)
        public_protocol = _add_experiment(other_user, 'public')  # Re-run case 2
        _add_experiment(other_user, 'public',  # Not re-run as other model
                        proto=public_protocol, proto_commit=public_protocol.repo.latest_commit,
                        model=other_model, model_commit=other_model_commit)
        _add_experiment(other_user, 'private')  # Not re-run as can't see protocol
        visible_protocol = _add_experiment(other_user, 'private', shared=True)  # Re-run case 3

        # Create a new version of our model, re-running experiments
        helpers.add_permission(logged_in_user, 'create_model')
        if route == 'main_form':
            recipes.model_file.make(
                entity=model,
                upload=SimpleUploadedFile('file2.txt', b'file 2'),
                original_name='file2.txt',
            )
            response = client.post(
                '/entities/models/%d/versions/new' % model.pk,
                data={
                    'filename[]': ['uploads/file2.txt'],
                    'mainEntry': ['file2.txt'],
                    'commit_message': 'new',
                    'visibility': 'private',
                    'tag': '',
                    'rerun_expts': '1',
                },
            )
            assert response.status_code == 302
            new_commit = model.repo.latest_commit
            assert response.url == '/entities/models/%d/versions/%s' % (model.id, new_commit.sha)
        else:
            assert route == 'edit_file'
            response = client.post('/entities/models/%d/versions/edit' % model.id, json.dumps({
                'parent_hexsha': model_commit.sha,
                'file_name': 'file1.txt',
                'file_contents': 'new file 1',
                'visibility': 'private',
                'tag': '',
                'commit_message': 'edit',
                'rerun_expts': True,
            }), content_type='application/json')
            assert response.status_code == 200
            detail = json.loads(response.content.decode())
            assert 'updateEntityFile' in detail
            assert detail['updateEntityFile']['response']
            new_commit = model.repo.latest_commit
            assert detail['updateEntityFile']['url'] == '/entities/models/%d/versions/%s' % (
                model.id, new_commit.sha)

        # Test that planned experiments have been added correctly
        expected_proto_versions = set([
            (my_private_protocol, my_private_protocol.repo.latest_commit.sha),
            (public_protocol, public_protocol.repo.latest_commit.sha),
            (visible_protocol, visible_protocol.repo.latest_commit.sha),
        ])
        assert len(expected_proto_versions) == PlannedExperiment.objects.count()
        for planned_experiment in PlannedExperiment.objects.all():
            assert planned_experiment.submitter == logged_in_user
            assert planned_experiment.model == model
            assert planned_experiment.model_version == new_commit.sha
            assert (planned_experiment.protocol, planned_experiment.protocol_version) in expected_proto_versions


@pytest.mark.django_db
class TestAlterFileView:
    def test_requires_login(self, client):
        model = recipes.model.make()
        response = client.post('/entities/models/%d/versions/edit' % model.pk, {})
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_cannot_alter_as_non_owner(self, logged_in_user, client):
        model = recipes.model.make()
        response = client.post('/entities/models/%d/versions/edit' % model.pk, {})
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_error_if_bad_args(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        first_commit = helpers.add_version(model, tag_name='v1')

        # Bad parent SHA
        response = client.post('/entities/models/%d/versions/edit' % model.id, json.dumps({
            'parent_hexsha': '',
            'file_name': 'file1.txt',
            'file_contents': 'new file 1',
            'visibility': 'private',
            'tag': '',
            'commit_message': 'edit',
            'rerun_expts': False,
        }), content_type='application/json')
        assert response.status_code == 200
        assert model.repo.latest_commit == first_commit
        detail = json.loads(response.content.decode())['updateEntityFile']
        assert not detail['response']
        assert 'newer version' in detail['responseText']

        # Wrong file name
        response = client.post('/entities/models/%d/versions/edit' % model.id, json.dumps({
            'parent_hexsha': first_commit.sha,
            'file_name': 'file2.txt',
            'file_contents': 'new file 1',
            'visibility': 'private',
            'tag': '',
            'commit_message': 'edit',
            'rerun_expts': False,
        }), content_type='application/json')
        assert response.status_code == 200
        assert model.repo.latest_commit == first_commit
        detail = json.loads(response.content.decode())['updateEntityFile']
        assert not detail['response']
        assert 'file name provided does not exist' in detail['responseText']

        # Missing arg
        response = client.post('/entities/models/%d/versions/edit' % model.id, json.dumps({
            'parent_hexsha': first_commit.sha,
            'file_name': 'file1.txt',
            'tag': '',
        }), content_type='application/json')
        assert response.status_code == 200
        assert model.repo.latest_commit == first_commit
        detail = json.loads(response.content.decode())['updateEntityFile']
        assert not detail['response']
        assert 'missing required argument' in detail['responseText']

    def test_errors_if_no_change(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        first_commit = helpers.add_version(model, tag_name='v1', contents='initial file 1')

        response = client.post('/entities/models/%d/versions/edit' % model.id, json.dumps({
            'parent_hexsha': first_commit.sha,
            'file_name': 'file1.txt',
            'file_contents': 'initial file 1',
            'visibility': 'private',
            'tag': 'v1',
            'commit_message': 'edit',
            'rerun_expts': False,
        }), content_type='application/json')
        assert response.status_code == 200
        assert model.repo.latest_commit == first_commit
        detail = json.loads(response.content.decode())['updateEntityFile']
        assert not detail['response']
        assert 'identical to parent' in detail['responseText']

    def test_resets_on_add_error(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        first_commit = helpers.add_version(model, tag_name='v1', contents='initial file 1')

        with patch('entities.repository.Repository.add_file', side_effect=GitCommandError('add', 1, 'error')):
            response = client.post('/entities/models/%d/versions/edit' % model.id, json.dumps({
                'parent_hexsha': first_commit.sha,
                'file_name': 'file1.txt',
                'file_contents': 'new file 1',
                'visibility': 'private',
                'tag': '',
                'commit_message': 'edit',
                'rerun_expts': False,
            }), content_type='application/json')
        assert response.status_code == 200
        assert model.repo.latest_commit == first_commit
        with (model.repo_abs_path / 'file1.txt').open() as f:
            assert f.read() == 'initial file 1'
        detail = json.loads(response.content.decode())['updateEntityFile']
        assert not detail['response']
        assert 'failed to add new file version' in detail['responseText']

    def test_rolls_back_on_tag_error(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        first_commit = helpers.add_version(model, tag_name='v1', contents='initial file 1')

        response = client.post('/entities/models/%d/versions/edit' % model.id, json.dumps({
            'parent_hexsha': first_commit.sha,
            'file_name': 'file1.txt',
            'file_contents': 'new file 1',
            'visibility': 'private',
            'tag': 'v1',
            'commit_message': 'edit',
            'rerun_expts': False,
        }), content_type='application/json')
        assert response.status_code == 200
        assert model.repo.latest_commit == first_commit
        with (model.repo_abs_path / 'file1.txt').open() as f:
            assert f.read() == 'initial file 1'
        detail = json.loads(response.content.decode())['updateEntityFile']
        assert not detail['response']
        assert 'failed to tag' in detail['responseText']

    def test_without_rerun(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        first_commit = helpers.add_version(model, tag_name='v1', contents='initial file 1')

        response = client.post('/entities/models/%d/versions/edit' % model.id, json.dumps({
            'parent_hexsha': first_commit.sha,
            'file_name': 'file1.txt',
            'file_contents': 'new file 1',
            'visibility': 'private',
            'tag': '',
            'commit_message': 'edit',
            'rerun_expts': False,
        }), content_type='application/json')
        assert response.status_code == 200
        new_commit = model.repo.latest_commit
        assert new_commit != first_commit
        with (model.repo_abs_path / 'file1.txt').open() as f:
            assert f.read() == 'new file 1'
        detail = json.loads(response.content.decode())['updateEntityFile']
        assert detail['response']
        assert detail['url'] == '/entities/models/%d/versions/%s' % (
            model.id, new_commit.sha)
        assert 0 == PlannedExperiment.objects.count()


@pytest.mark.django_db
class TestCheckProtocolCallbackView:
    @patch('requests.post')
    def test_stores_empty_interface(self, mock_post, client, analysis_task):
        task_id = str(analysis_task.id)
        protocol = analysis_task.entity
        hexsha = analysis_task.version
        version = protocol.repocache.get_version(hexsha)

        # Check there is no interface initially
        assert not version.interface.exists()
        assert not protocol.is_parsed_ok(version)

        # Submit the fake task response
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': task_id,
            'returntype': 'success',
            'required': [],
            'optional': [],
        }), content_type='application/json')
        assert response.status_code == 200

        # Check the analysis task has been deleted
        assert not AnalysisTask.objects.filter(id=task_id).exists()

        # Check there is a blank interface term
        assert version.interface.count() == 1
        assert version.interface.get().term == ''
        assert version.interface.get().optional

        # Check parsing is treated as having happened OK
        version.refresh_from_db()
        assert protocol.is_parsed_ok(version)

        # Check submitting a new task is now a no-op
        from entities.processing import submit_check_protocol_task
        submit_check_protocol_task(protocol, hexsha)

        assert not mock_post.called
        assert not AnalysisTask.objects.filter(entity=protocol).exists()

    def test_stores_actual_interface(self, client, analysis_task):
        task_id = str(analysis_task.id)
        protocol = analysis_task.entity
        hexsha = analysis_task.version
        version = protocol.repocache.get_version(hexsha)

        # Check there is no interface initially
        assert not version.interface.exists()
        assert not protocol.is_parsed_ok(version)

        # Submit the fake task response
        req = ['r1', 'r2']
        opt = ['o1']
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': task_id,
            'returntype': 'success',
            'required': req,
            'optional': opt,
        }), content_type='application/json')
        assert response.status_code == 200

        # Check the analysis task has been deleted
        assert not AnalysisTask.objects.filter(id=task_id).exists()

        # Check parsing is treated as having happened OK
        version.refresh_from_db()
        assert protocol.is_parsed_ok(version)

        # Check the terms are as expected
        assert version.interface.count() == len(req) + len(opt)
        assert set(version.interface.values_list('term', flat=True)) == set(req) | set(opt)
        for term in version.interface.all():
            if term.term in opt:
                assert term.optional
            else:
                assert term.term in req
                assert not term.optional

    @patch('requests.post')
    def test_stores_error_response(self, mock_post, client, analysis_task):
        task_id = str(analysis_task.id)
        protocol = analysis_task.entity
        hexsha = analysis_task.version
        version = protocol.repocache.get_version(hexsha)

        # Check there is no interface or error file initially
        assert not version.interface.exists()
        assert not protocol.is_parsed_ok(version)
        commit = protocol.repo.get_commit(hexsha)
        assert 'errors.txt' not in commit.filenames

        # Submit the fake task response
        msg = 'My test error message'
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': task_id,
            'returntype': 'failed',
            'returnmsg': msg,
        }), content_type='application/json')
        assert response.status_code == 200

        # Check the analysis task has been deleted
        assert not AnalysisTask.objects.filter(id=task_id).exists()

        # Check parsing is not OK this time
        version.refresh_from_db()
        assert not protocol.is_parsed_ok(version)

        # Check there's an ephemeral error file
        commit = protocol.repo.get_commit(hexsha)
        assert 'errors.txt' in commit.filenames
        assert msg in commit.get_blob('errors.txt').data_stream.read().decode('UTF-8')

        # Check submitting a new task is now a no-op
        from entities.processing import submit_check_protocol_task
        submit_check_protocol_task(protocol, hexsha)

        assert not mock_post.called
        assert not AnalysisTask.objects.filter(entity=protocol).exists()

    def test_errors_on_duplicate_terms(self, client, analysis_task):
        # Submit the fake task response
        req = ['r1', 'r2']
        opt = ['o1', 'r2']
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': str(analysis_task.id),
            'returntype': 'success',
            'required': req,
            'optional': opt,
        }), content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['error'].startswith('duplicate term provided: ')

    def test_errors_on_no_signature(self, client):
        response = client.post('/entities/callback/check-proto', json.dumps({
            'returntype': 'failed',
        }), content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['error'] == 'missing signature'

    def test_errors_on_bad_signature(self, client):
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': str(uuid.uuid4()),
        }), content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['error'] == 'invalid signature'

    def test_errors_on_missing_returntype(self, client):
        analysis_task = recipes.analysis_task.make()
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': str(analysis_task.id),
        }), content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['error'] == 'missing returntype'

    def test_errors_on_missing_terms(self, client):
        analysis_task = recipes.analysis_task.make()
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': str(analysis_task.id),
            'returntype': 'success',
        }), content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['error'] == 'missing terms'


@pytest.mark.django_db
class TestEntityFileDownloadView:
    def test_download_file(self, client, public_model):
        version = public_model.repo.latest_commit

        response = client.get(
            '/entities/models/%d/versions/%s/download/file1.txt' %
            (public_model.pk, version.sha)
        )

        assert response.status_code == 200
        assert response.content == b'entity contents'
        assert response['Content-Disposition'] == (
            'attachment; filename=file1.txt'
        )
        assert response['Content-Type'] == 'text/plain'

    @pytest.mark.parametrize("filename", [
        ('oxmeta:membrane-voltage with spaces.csv'),
        ('oxmeta%3Amembrane_voltage.csv'),
    ])
    def test_handles_odd_characters(self, client, helpers, filename):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public', filename=filename)

        response = client.get(
            reverse('entities:file_download', args=['model', model.pk, v1.sha, filename])
        )

        assert response.status_code == 200
        assert response.content == b'entity contents'
        assert response['Content-Disposition'] == (
            'attachment; filename=' + filename
        )
        assert response['Content-Type'] == 'text/csv'

    @pytest.mark.parametrize("filename", [
        ('/etc/passwd'),
        ('../../../../../pytest.ini'),
    ])
    def test_disallows_non_local_files(self, client, public_model, filename):
        version = public_model.repo.latest_commit

        response = client.get(
            '/entities/models/%d/versions/%s/download/%s' %
            (public_model.pk, version.sha, filename)
        )

        assert response.status_code == 404

    @patch('mimetypes.guess_type', return_value=(None, None))
    def test_uses_octet_stream_for_unknown_file_type(self, mock_guess, client, public_model):
        version = public_model.repo.latest_commit

        response = client.get(
            '/entities/models/%d/versions/%s/download/file1.txt' %
            (public_model.pk, version.sha)
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/octet-stream'

    def test_returns_404_for_nonexistent_file(self, client, public_model):
        version = public_model.repo.latest_commit
        response = client.get(
            '/entities/models/%d/versions/%s/download/nonexistent.txt' %
            (public_model.pk, version.sha)
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestEntityArchiveView:
    def test_download_archive(self, client, helpers):
        model = recipes.model.make()
        commit = helpers.add_version(model, filename='file1.txt', visibility='public')

        response = client.get('/entities/models/%d/versions/latest/archive' % model.pk)
        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert archive.filelist[0].filename == 'file1.txt'
        assert response['Content-Disposition'] == (
            'attachment; filename=%s_%s.zip' % (model.name, commit.sha)
        )

    def test_returns_404_if_no_commits_yet(self, logged_in_user, client):
        model = recipes.model.make()

        response = client.get('/entities/models/%d/versions/latest/archive' % model.pk)
        assert response.status_code == 404

    def test_anonymous_model_download_for_running_experiment(self, client, queued_experiment):
        model = queued_experiment.experiment.model
        sha = model.repo.latest_commit.sha
        queued_experiment.experiment.model.set_version_visibility(sha, 'private')

        response = client.get(
            '/entities/models/%d/versions/latest/archive' % model.pk,
            HTTP_AUTHORIZATION='Token {}'.format(queued_experiment.signature)
        )

        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert archive.filelist[0].filename == 'file1.txt'

    def test_anonymous_protocol_download_for_running_experiment(self, client, queued_experiment):
        protocol = queued_experiment.experiment.protocol
        protocol.set_version_visibility('latest', 'private')

        response = client.get(
            '/entities/protocols/%d/versions/latest/archive' % protocol.pk,
            HTTP_AUTHORIZATION='Token {}'.format(queued_experiment.signature)
        )

        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert archive.filelist[0].filename == 'file1.txt'

    def test_anonymous_protocol_download_for_analysis_task(self, client, analysis_task):
        protocol = analysis_task.entity
        protocol.set_version_visibility('latest', 'private')

        response = client.get(
            '/entities/protocols/%d/versions/latest/archive' % protocol.pk,
            HTTP_AUTHORIZATION='Token {}'.format(analysis_task.id)
        )

        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert archive.filelist[0].filename == 'file1.txt'

    def test_public_entity_still_visible_with_invalid_token(self, client, queued_experiment):
        model = queued_experiment.experiment.model
        queued_experiment.experiment.model.set_version_visibility('latest', 'public')

        response = client.get(
            '/entities/models/%d/versions/latest/archive' % model.pk,
            HTTP_AUTHORIZATION='Token {}'.format(uuid.uuid4())
        )

        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert archive.filelist[0].filename == 'file1.txt'


@pytest.mark.django_db
class TestFileUpload:
    def test_upload_file(self, logged_in_user, client):
        model = recipes.model.make(author=logged_in_user)

        upload = io.StringIO('my test model')
        upload.name = 'model.txt'
        response = client.post(
            '/entities/%d/upload-file' % model.pk,
            {
                'upload': upload
            }
        )

        data = json.loads(response.content.decode())
        upload = data['files'][0]
        assert upload['stored_name'] == 'uploads/model.txt'
        assert upload['name'] == 'model.txt'
        assert upload['is_valid']
        assert upload['size'] == 13

        assert model.files.count() == 1

    def test_bad_upload(self, logged_in_user, client):
        model = recipes.model.make(author=logged_in_user)

        response = client.post('/entities/%d/upload-file' % model.pk, {})

        assert response.status_code == 400


@pytest.mark.django_db
class TestEntityCollaboratorsView:
    def test_anonymous_cannot_view_page(self, client):
        model = recipes.model.make()
        response = client.get('/entities/models/%d/collaborators' % model.pk)
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_non_owner_cannot_view_page(self, logged_in_user, client):
        model = recipes.model.make()
        response = client.get('/entities/models/%d/collaborators' % model.pk)
        assert response.status_code == 403

    def test_owner_can_view_page(self, logged_in_user, client):
        model = recipes.model.make(author=logged_in_user)
        response = client.get('/entities/models/%d/collaborators' % model.pk)
        assert response.status_code == 200
        assert 'formset' in response.context

    def test_superuser_can_view_page(self, logged_in_admin, client):
        model = recipes.model.make()
        response = client.get('/entities/models/%d/collaborators' % model.pk)
        assert response.status_code == 200
        assert 'formset' in response.context

    def test_loads_existing_collaborators(self, logged_in_user, other_user, client):
        model = recipes.model.make(author=logged_in_user)
        assign_perm('edit_entity', other_user, model)
        response = client.get('/entities/models/%d/collaborators' % model.pk)
        assert response.status_code == 200
        assert response.context['formset'][0]['email'].value() == other_user.email

    def test_add_editor(self, logged_in_user, other_user, helpers, client):
        helpers.add_permission(other_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        response = client.post('/entities/models/%d/collaborators' % model.pk,
                               {
                                   'form-0-email': other_user.email,
                                   'form-TOTAL_FORMS': 1,
                                   'form-MAX_NUM_FORMS': 1,
                                   'form-MIN_NUM_FORMS': 0,
                                   'form-INITIAL_FORMS': 0,
                               })
        assert response.status_code == 302
        assert other_user.has_perm('edit_entity', model)

    def test_add_non_existent_user_as_editor(self, logged_in_user, client):
        model = recipes.model.make(author=logged_in_user)
        response = client.post('/entities/models/%d/collaborators' % model.pk,
                               {
                                   'form-0-email': 'non-existent@example.com',
                                   'form-TOTAL_FORMS': 1,
                                   'form-MAX_NUM_FORMS': 1,
                                   'form-MIN_NUM_FORMS': 0,
                                   'form-INITIAL_FORMS': 0,
                               })
        assert response.status_code == 200
        assert 'email' in response.context['formset'][0].errors

    def test_remove_editor(self, logged_in_user, other_user, helpers, client):
        model = recipes.model.make(author=logged_in_user)
        helpers.add_permission(other_user, 'create_model')
        assign_perm('edit_entity', other_user, model)
        response = client.post('/entities/models/%d/collaborators' % model.pk,
                               {
                                   'form-0-DELETE': 'on',
                                   'form-0-email': other_user.email,
                                   'form-TOTAL_FORMS': 1,
                                   'form-MAX_NUM_FORMS': 1,
                                   'form-MIN_NUM_FORMS': 0,
                                   'form-INITIAL_FORMS': 1,
                               })
        assert response.status_code == 302
        assert not other_user.has_perm('edit_entity', model)

    def test_non_owner_cannot_edit(self, logged_in_user, client):
        model = recipes.model.make()
        response = client.post('/entities/models/%d/collaborators' % model.pk, {})
        assert response.status_code == 403

    def test_anonymous_cannot_edit(self, client):
        model = recipes.model.make()
        response = client.post('/entities/models/%d/collaborators' % model.pk, {})
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_superuser_can_edit(self, client, logged_in_admin, model_creator):
        model = recipes.model.make()
        response = client.post('/entities/models/%d/collaborators' % model.pk,
                               {
                                   'form-0-email': model_creator.email,
                                   'form-TOTAL_FORMS': 1,
                                   'form-MAX_NUM_FORMS': 1,
                                   'form-MIN_NUM_FORMS': 0,
                                   'form-INITIAL_FORMS': 0,
                               })
        assert response.status_code == 302
        assert model_creator.has_perm('edit_entity', model)


@pytest.mark.django_db
class TestEntityDiffView:
    def test_unix_diff(self, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, contents='v1 contents\n', visibility='public')
        v2 = helpers.add_version(model, contents='v2 contents\n', visibility='public')

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)
        response = client.get(
            '/entities/models/diff/%s/%s/file1.txt?type=unix' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['getUnixDiff']['unixDiff'] == '''1c1
< v1 contents
---
> v2 contents
'''
        assert data['getUnixDiff']['response']

    def test_error_for_invalid_diff_type(self, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        v2 = helpers.add_version(model, visibility='private')

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)
        response = client.get(
            '/entities/models/diff/%s/%s/file1.txt?type=invalid' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['error']

    def test_cannot_diff_entities_with_no_access(self, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        v2 = helpers.add_version(model, visibility='private')

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)
        response = client.get(
            '/entities/models/diff/%s/%s/file1.txt' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'response' not in data['getUnixDiff']

    def test_can_diff_entities_if_collaborator(self, client, logged_in_user, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        v2 = helpers.add_version(model, visibility='private')
        assign_perm('edit_entity', logged_in_user, model)

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)
        response = client.get(
            '/entities/models/diff/%s/%s/file1.txt' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['getUnixDiff']['response']

    @patch('subprocess.run')
    def test_unix_diff_returns_error_on_process_error(self, mock_run, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, contents='v1 contents\n', visibility='public')
        v2 = helpers.add_version(model, contents='v2 contents\n', visibility='public')

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)

        mock_run.side_effect = SubprocessError('something went wrong')

        response = client.get(
            '/entities/models/diff/%s/%s/file1.txt?type=unix' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'response' not in data['getUnixDiff']
        assert data['getUnixDiff']['responseText'] == (
            "Couldn't compute unix diff (something went wrong)")

    @patch('requests.post')
    def test_bives_diff(self, mock_post, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, contents='v1 contents\n', visibility='public')
        v2 = helpers.add_version(model, contents='v2 contents\n', visibility='public')

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)

        mock_post.return_value.json.return_value = {
            'bivesDiff': 'diff-contents',
        }

        response = client.get(
            '/entities/models/diff/%s/%s/file1.txt?type=bives' % (v1_spec, v2_spec)
        )

        mock_post.assert_called_with(
            'https://bives.bio.informatik.uni-rostock.de/',
            json={
                'files': [
                    'v1 contents' + os.linesep,
                    'v2 contents' + os.linesep
                ],
                'commands': [
                    'compHierarchyJson',
                    'reactionsJson',
                    'reportHtml',
                    'xmlDiff',
                ]})

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['getBivesDiff']['bivesDiff'] == {'bivesDiff': 'diff-contents'}
        assert data['getBivesDiff']['response']

    @patch('requests.post')
    def test_bives_diff_returns_error_on_server_error(self, mock_post, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, contents='v1 contents\n', visibility='public')
        v2 = helpers.add_version(model, contents='v2 contents\n', visibility='public')

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)

        mock_post.return_value.ok = False
        mock_post.return_value.status_code = 400
        mock_post.return_value.content = b'Server error'

        response = client.get(
            '/entities/models/diff/%s/%s/file1.txt?type=bives' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'response' not in data['getBivesDiff']
        assert data['getBivesDiff']['responseText'] == 'bives request failed: 400 (Server error)'

    @patch('requests.post')
    def test_bives_diff_returns_error_on_server_error_message(self, mock_post, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, contents='v1 contents\n', visibility='public')
        v2 = helpers.add_version(model, contents='v2 contents\n', visibility='public')

        v1_spec = '%d:%s' % (model.pk, v1.sha)
        v2_spec = '%d:%s' % (model.pk, v2.sha)

        mock_post.return_value.json.return_value = {
            'error': ['error-message'],
        }

        response = client.get(
            '/entities/models/diff/%s/%s/file1.txt?type=bives' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'response' not in data['getBivesDiff']
        assert data['getBivesDiff']['responseText'] == 'error-message'


@pytest.mark.django_db
@pytest.mark.parametrize("recipe,url", [
    (recipes.model, '/entities/models/%d'),
    (recipes.model, '/entities/models/%d/versions/'),
    (recipes.model, '/entities/models/%d/versions/latest'),
    (recipes.model, '/entities/models/%d/versions/latest/compare'),
    (recipes.model, '/entities/models/%d/versions/latest/archive'),
    (recipes.model, '/entities/models/%d/versions/latest/files.json'),
    (recipes.model, '/entities/models/%d/versions/latest/download/file1.txt'),
    (recipes.protocol, '/entities/protocols/%d'),
    (recipes.protocol, '/entities/protocols/%d/versions/'),
    (recipes.protocol, '/entities/protocols/%d/versions/latest'),
    (recipes.protocol, '/entities/protocols/%d/versions/latest/compare'),
    (recipes.protocol, '/entities/protocols/%d/versions/latest/archive'),
    (recipes.protocol, '/entities/protocols/%d/versions/latest/files.json'),
    (recipes.protocol, '/entities/protocols/%d/versions/latest/download/file1.txt'),
])
class TestEntityVisibility:
    def test_private_entity_visible_to_self(self, client, logged_in_user, helpers, recipe, url):
        entity = recipe.make(author=logged_in_user)
        helpers.add_version(entity, visibility='private')
        assert client.get(url % entity.pk, follow=True).status_code == 200

    def test_private_entity_visible_to_collaborator(self, client, logged_in_user, helpers, recipe, url):
        entity = recipe.make()
        helpers.add_version(entity, visibility='private')
        assign_perm('edit_entity', logged_in_user, entity)
        assert client.get(url % entity.pk, follow=True).status_code == 200

    def test_private_entity_invisible_to_other_user(
        self,
        client, logged_in_user, other_user, helpers,
        recipe, url
    ):
        entity = recipe.make(author=other_user)
        helpers.add_version(entity, visibility='private')
        response = client.get(url % entity.pk)
        assert response.status_code == 404

    def test_private_entity_requires_login_for_anonymous(self, client, helpers, recipe, url):
        entity = recipe.make()
        helpers.add_version(entity, visibility='private')
        response = client.get(url % entity.pk)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_public_entity_visible_to_anonymous(self, client, helpers, recipe, url):
        entity = recipe.make()
        helpers.add_version(entity, visibility='public')
        assert client.get(url % entity.pk, follow=True).status_code == 200

    def test_public_entity_visible_to_logged_in_user(self, client, logged_in_user, helpers, recipe, url):
        entity = recipe.make()
        helpers.add_version(entity, visibility='public')
        assert client.get(url % entity.pk, follow=True).status_code == 200

    def test_nonexistent_entity_redirects_anonymous_to_login(self, client, helpers, recipe, url):
        response = client.get(url % 10000)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_nonexistent_entity_generates_404_for_user(self, client, logged_in_user, helpers, recipe, url):
        response = client.get(url % 10000)
        assert response.status_code == 404


@pytest.mark.django_db
class TestEntityRunExperiment:
    def test_view_run_experiment_model(self, client, helpers, logged_in_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        helpers.add_version(model, visibility='private')
        protocol = recipes.protocol.make(author=logged_in_user)
        commit1 = helpers.add_version(protocol, visibility='public')
        commit2 = helpers.add_version(protocol, visibility='public')
        protocol.add_tag('v1', commit2.sha)

        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, 'latest'))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'name': 'myprotocol1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['preposition'] == 'under'

    def test_view_run_experiment_model_multiple_users(self, client, helpers, logged_in_user, other_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        helpers.add_version(model, visibility='moderated')

        protocol = recipes.protocol.make(author=logged_in_user)
        commit1 = helpers.add_version(protocol, visibility='public')
        commit2 = helpers.add_version(protocol, visibility='public')
        protocol.add_tag('v1', commit2.sha)

        other_protocol = recipes.protocol.make(author=other_user)
        other_commit1 = helpers.add_version(other_protocol, visibility='public')
        other_commit2 = helpers.add_version(other_protocol, visibility='public')
        other_protocol.add_tag('v1', other_commit2.sha)

        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, 'latest'))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'name': 'myprotocol1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['other_object_list'] == [
            {'id': other_protocol.pk,
             'name': 'myprotocol2',
             'versions': [{'commit': other_commit2, 'tags': ['v1'], 'latest': True},
                          {'commit': other_commit1, 'tags': [], 'latest': False}]},
        ]
        assert response.context['preposition'] == 'under'

    def test_view_run_experiment_model_post(self, client, helpers, logged_in_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        commit_model = helpers.add_version(model, visibility='public')

        protocol = recipes.protocol.make(author=logged_in_user)
        commit1 = helpers.add_version(protocol, visibility='public')
        commit2 = helpers.add_version(protocol, visibility='public')
        protocol.add_tag('v1', commit2.sha)

        # Test context has correct information
        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'name': 'myprotocol1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        # Test post returns correct response
        data = {'model_protocol_list[]': ['%d:%s' % (protocol.pk, commit2.sha)],
                'rerun_expts': 'on'}
        response = client.post(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha),
            data=data)
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/latest' % model.pk

        # Test that planned experiments have been added correctly
        expected_proto_versions = set([
            (protocol, commit2.sha)
        ])
        assert PlannedExperiment.objects.count() == 1
        for planned_experiment in PlannedExperiment.objects.all():
            assert planned_experiment.submitter == logged_in_user
            assert planned_experiment.model == model
            assert planned_experiment.model_version == commit_model.sha
            assert (planned_experiment.protocol, planned_experiment.protocol_version) in expected_proto_versions

    def test_view_run_experiment_model_post_exclude_existing(self, client, helpers, logged_in_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        commit_model = helpers.add_version(model, visibility='public')

        protocol = recipes.protocol.make(author=logged_in_user)
        commit1 = helpers.add_version(protocol, visibility='public')
        commit2 = helpers.add_version(protocol, visibility='public')
        protocol.add_tag('v1', commit2.sha)

        recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=model,
            experiment__model_version=commit_model.sha,
            experiment__protocol=protocol,
            experiment__protocol_version=commit1.sha)

        # Test context has correct information
        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'name': 'myprotocol1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        # Test post returns correct response
        data = {'model_protocol_list[]': ['%d:%s' % (protocol.pk, commit1.sha),
                                          '%d:%s' % (protocol.pk, commit2.sha)],
                }
        response = client.post(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha),
            data=data)
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/latest' % model.pk

        # Test that planned experiments have been added correctly
        expected_proto_versions = set([
            (protocol, commit2.sha)
        ])
        assert PlannedExperiment.objects.count() == 1
        for planned_experiment in PlannedExperiment.objects.all():
            assert planned_experiment.submitter == logged_in_user
            assert planned_experiment.model == model
            assert planned_experiment.model_version == commit_model.sha
            assert (planned_experiment.protocol, planned_experiment.protocol_version) in expected_proto_versions

    def test_view_run_experiment_post_model_multiple_users(self, client, helpers, logged_in_user, other_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        commit_model = helpers.add_version(model, visibility='public')

        protocol = recipes.protocol.make(author=logged_in_user)
        commit1 = helpers.add_version(protocol, visibility='public')
        commit2 = helpers.add_version(protocol, visibility='public')
        protocol.add_tag('v1', commit2.sha)

        other_protocol = recipes.protocol.make(author=other_user)
        other_commit1 = helpers.add_version(other_protocol, visibility='public')
        other_commit2 = helpers.add_version(other_protocol, visibility='public')
        other_protocol.add_tag('v1', other_commit2.sha)

        # check context
        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'name': 'myprotocol1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['other_object_list'] == [
            {'id': other_protocol.pk,
             'name': 'myprotocol2',
             'versions': [{'commit': other_commit2, 'tags': ['v1'], 'latest': True},
                          {'commit': other_commit1, 'tags': [], 'latest': False}]},
        ]
        # Test post returns correct response
        data = {'model_protocol_list[]': ['%d:%s' % (protocol.pk, commit2.sha),
                                          '%d:%s' % (other_protocol.pk, other_commit1.sha),
                                          '%d:%s' % (other_protocol.pk, other_commit2.sha)],
                'rerun_expts': 'on'}
        response = client.post(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha),
            data=data)
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/latest' % model.pk

        # Test that planned experiments have been added correctly
        expected_proto_versions = set([
            (protocol, commit2.sha),
            (other_protocol, other_commit1.sha),
            (other_protocol, other_commit2.sha)
        ])
        assert PlannedExperiment.objects.count() == 3
        for planned_experiment in PlannedExperiment.objects.all():
            assert planned_experiment.submitter == logged_in_user
            assert planned_experiment.model == model
            assert planned_experiment.model_version == commit_model.sha
            assert (planned_experiment.protocol, planned_experiment.protocol_version) in expected_proto_versions

    def test_view_run_experiment_model_not_latest(self, client, helpers, logged_in_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        helpers.add_version(model, visibility='private')
        model_commit1 = helpers.add_version(model, visibility='public')
        model.add_tag('model_v1', model_commit1.sha)
        model_commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('model_v2', model_commit2.sha)
        protocol = recipes.protocol.make(author=logged_in_user)
        commit1 = helpers.add_version(protocol, visibility='public')
        commit2 = helpers.add_version(protocol, visibility='public')
        protocol.add_tag('v1', commit2.sha)

        # display page using tag
        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, 'model_v1'))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'name': 'myprotocol1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['preposition'] == 'under'

        # Test post returns correct response
        data = {'model_protocol_list[]': ['%d:%s' % (protocol.pk, commit2.sha),
                                          '%d:%s' % (protocol.pk, commit1.sha)],
                'rerun_expts': 'on'}
        response = client.post(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, 'model_v1'),
            data=data)
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/model_v1' % model.pk

        # Test that planned experiments have been added correctly
        expected_proto_versions = set([
            (protocol, commit2.sha),
            (protocol, commit1.sha),
        ])
        assert PlannedExperiment.objects.count() == 2
        for planned_experiment in PlannedExperiment.objects.all():
            assert planned_experiment.submitter == logged_in_user
            assert planned_experiment.model == model
            assert planned_experiment.model_version == model_commit1.sha
            assert (planned_experiment.protocol, planned_experiment.protocol_version) in expected_proto_versions

    # repeat tests with protocol as the calling entity
    def test_view_run_experiment_protocol(self, client, helpers, logged_in_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        commit1 = helpers.add_version(model, visibility='public')
        commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('v1', commit2.sha)
        protocol = recipes.protocol.make(author=logged_in_user)
        helpers.add_version(protocol, visibility='private')

        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, 'latest'))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'name': 'mymodel1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['preposition'] == 'on'

    def test_view_run_experiment_protocol_multiple_users(self, client, helpers, logged_in_user, other_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        commit1 = helpers.add_version(model, visibility='public')
        commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('v1', commit2.sha)

        other_model = recipes.model.make(author=other_user)
        other_commit1 = helpers.add_version(other_model, visibility='public')
        other_commit2 = helpers.add_version(other_model, visibility='public')
        other_model.add_tag('v1', other_commit2.sha)

        protocol = recipes.protocol.make(author=logged_in_user)
        helpers.add_version(protocol, visibility='private')

        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, 'latest'))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'name': 'mymodel1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['other_object_list'] == [
            {'id': other_model.pk,
             'name': 'mymodel2',
             'versions': [{'commit': other_commit2, 'tags': ['v1'], 'latest': True},
                          {'commit': other_commit1, 'tags': [], 'latest': False}]},
        ]
        assert response.context['preposition'] == 'on'

    def test_view_run_experiment_protocol_post(self, client, helpers, logged_in_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        commit1 = helpers.add_version(model, visibility='public')
        commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('v1', commit2.sha)
        protocol = recipes.protocol.make(author=logged_in_user)
        commit_protocol = helpers.add_version(protocol, visibility='public')

        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, commit_protocol.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'name': 'mymodel1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        # Test post returns correct response
        data = {'model_protocol_list[]': ['%d:%s' % (model.pk, commit1.sha), '%d:%s' % (model.pk, commit2.sha)],
                'rerun_expts': 'on'}
        response = client.post(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, commit_protocol.sha),
            data=data)
        assert response.status_code == 302
        assert response.url == '/entities/protocols/%d/versions/latest' % protocol.pk

        # Test that planned experiments have been added correctly
        expected_model_versions = set([
            (model, commit2.sha),
            (model, commit1.sha)
        ])
        assert PlannedExperiment.objects.count() == 2
        for planned_experiment in PlannedExperiment.objects.all():
            assert planned_experiment.submitter == logged_in_user
            assert planned_experiment.protocol == protocol
            assert planned_experiment.protocol_version == commit_protocol.sha
            assert (planned_experiment.model, planned_experiment.model_version) in expected_model_versions

    def test_view_run_experiment_protocol_post_exclude_existing(self, client, helpers, logged_in_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        commit1 = helpers.add_version(model, visibility='public')
        commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('v1', commit2.sha)
        protocol = recipes.protocol.make(author=logged_in_user)
        commit_protocol = helpers.add_version(protocol, visibility='public')

        recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=model,
            experiment__model_version=commit1.sha,
            experiment__protocol=protocol,
            experiment__protocol_version=commit_protocol.sha)
        # This experiment has no versions so should not be excluded
        recipes.experiment.make(
            model=model,
            model_version=commit2.sha,
            protocol=protocol,
            protocol_version=commit_protocol.sha)

        # Test context has correct information
        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, commit_protocol.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'name': 'mymodel1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        # Test post returns correct response
        data = {'model_protocol_list[]': ['%d:%s' % (model.pk, commit1.sha), '%d:%s' % (model.pk, commit2.sha)],
                }
        response = client.post(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, commit_protocol.sha),
            data=data)
        assert response.status_code == 302
        assert response.url == '/entities/protocols/%d/versions/latest' % protocol.pk

        # Test that planned experiments have been added correctly
        expected_model_versions = set([
            (model, commit2.sha),
        ])
        assert PlannedExperiment.objects.count() == 1
        for planned_experiment in PlannedExperiment.objects.all():
            assert planned_experiment.submitter == logged_in_user
            assert planned_experiment.protocol == protocol
            assert planned_experiment.protocol_version == commit_protocol.sha
            assert (planned_experiment.model, planned_experiment.model_version) in expected_model_versions

    def test_view_run_experiment_post_protocol_multiple_users(self, client, helpers, logged_in_user, other_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        commit1 = helpers.add_version(model, visibility='public')
        commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('v1', commit2.sha)
        protocol = recipes.protocol.make(author=logged_in_user)
        commit_protocol = helpers.add_version(protocol, visibility='public')

        other_model = recipes.model.make(author=other_user)
        other_commit1 = helpers.add_version(other_model, visibility='public')
        other_commit2 = helpers.add_version(other_model, visibility='public')
        other_model.add_tag('v1', other_commit2.sha)

        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, commit_protocol.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'name': 'mymodel1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['other_object_list'] == [
            {'id': other_model.pk,
             'name': 'mymodel2',
             'versions': [{'commit': other_commit2, 'tags': ['v1'], 'latest': True},
                          {'commit': other_commit1, 'tags': [], 'latest': False}]},
        ]
        # Test post returns correct response
        data = {'model_protocol_list[]': ['%d:%s' % (model.pk, commit1.sha),
                                          '%d:%s' % (model.pk, commit2.sha),
                                          '%d:%s' % (other_model.pk, other_commit1.sha)],
                'rerun_expts': 'on'}
        response = client.post(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, commit_protocol.sha),
            data=data)
        assert response.status_code == 302
        assert response.url == '/entities/protocols/%d/versions/latest' % protocol.pk

        # Test that planned experiments have been added correctly
        expected_model_versions = set([
            (model, commit2.sha),
            (model, commit1.sha),
            (other_model, other_commit1.sha)
        ])
        assert PlannedExperiment.objects.count() == 3
        for planned_experiment in PlannedExperiment.objects.all():
            assert planned_experiment.submitter == logged_in_user
            assert planned_experiment.protocol == protocol
            assert planned_experiment.protocol_version == commit_protocol.sha
            assert (planned_experiment.model, planned_experiment.model_version) in expected_model_versions

    def test_view_run_experiment_none_checked(self, client, helpers, logged_in_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        commit_model = helpers.add_version(model, visibility='public')

        protocol = recipes.protocol.make(author=logged_in_user)
        commit1 = helpers.add_version(protocol, visibility='public')
        commit2 = helpers.add_version(protocol, visibility='public')
        protocol.add_tag('v1', commit2.sha)

        # Test context has correct information
        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'name': 'myprotocol1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        # Test post returns correct response
        data = {'model_protocol_list[]': [],
                'rerun_expts': 'on'}
        response = client.post(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha),
            data=data)
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/latest' % model.pk

        # Test that no planned experiments have been added
        assert PlannedExperiment.objects.count() == 0

        # Try again without re-running
        data = {'model_protocol_list[]': []}
        response = client.post(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha),
            data=data)
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/latest' % model.pk

        # Test that no planned experiments have been added
        assert PlannedExperiment.objects.count() == 0

    def test_view_run_experiment_protocol_not_latest(self, client, helpers, logged_in_user):
        helpers.add_permission(logged_in_user, 'create_experiment', Experiment)
        model = recipes.model.make(author=logged_in_user)
        commit1 = helpers.add_version(model, visibility='public')
        commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('v1', commit2.sha)
        protocol = recipes.protocol.make(author=logged_in_user)
        proto_commit1 = helpers.add_version(protocol, visibility='public')
        proto_commit2 = helpers.add_version(protocol, visibility='public')
        protocol.add_tag('p1', proto_commit1.sha)
        protocol.add_tag('p2', proto_commit2.sha)

        # display using sha
        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, proto_commit1.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'name': 'mymodel1',
                                                    'versions': [{'commit': commit2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': commit1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['preposition'] == 'on'

        # Test post returns correct response
        data = {'model_protocol_list[]': ['%d:%s' % (model.pk, commit1.sha), '%d:%s' % (model.pk, commit2.sha)],
                'rerun_expts': 'on'}
        response = client.post(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, proto_commit1.sha),
            data=data)
        assert response.status_code == 302
        assert response.url == '/entities/protocols/%d/versions/%s' % (protocol.pk, proto_commit1.sha)

        # Test that planned experiments have been added correctly
        expected_model_versions = set([
            (model, commit2.sha),
            (model, commit1.sha)
        ])
        assert PlannedExperiment.objects.count() == 2
        for planned_experiment in PlannedExperiment.objects.all():
            assert planned_experiment.submitter == logged_in_user
            assert planned_experiment.protocol == protocol
            assert planned_experiment.protocol_version == proto_commit1.sha
            assert (planned_experiment.model, planned_experiment.model_version) in expected_model_versions
