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
from django.core import mail
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from git import GitCommandError
from guardian.shortcuts import assign_perm

from core import recipes
from entities.models import (
    AnalysisTask,
    ModelEntity,
    ModelGroup,
    ProtocolEntity,
)
from experiments.models import Experiment, PlannedExperiment
from repocache.models import CachedProtocolVersion, ProtocolInterface, ProtocolIoputs
from repocache.populate import populate_entity_cache
from stories.models import StoryGraph


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

    def test_create_model_with_same_name(self, logged_in_user, other_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        helpers.add_permission(other_user, 'create_model')
        recipes.model.make(author=other_user, name='mymodel')
        response = client.post('/entities/models/new', data={
            'name': 'mymodel',
            'visibility': 'private',
        })
        assert response.status_code == 302

        assert ModelEntity.objects.count() == 2

    def test_create_model_requires_permissions(self, logged_in_user, client):
        response = client.post(
            '/entities/models/new',
            data={},
        )
        assert response.status_code == 403

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
        assert response.status_code == 403

    def test_error_if_later_version(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        helpers.add_version(model, tag_name='v1')

        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'parent_hexsha': '',
                'filename[]': ['file1.txt'],
                'delete_filename[]': [],
                'mainEntry': ['file1.txt'],
                'commit_message': 'files',
                'tag': 'v1',
                'visibility': 'public',
            },
        )

        assert response.status_code == 200
        assert "Someone has saved a newer version since you started " in response.rendered_content


@pytest.mark.django_db
class TestEntityRenaming:
    def test_model_renaming_success(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        assert model.name == 'my model1'

        response = client.post(
            '/entities/models/%d/rename' % model.pk,
            data={
                'name': 'new name'
            })
        assert response.status_code == 302
        entity = ModelEntity.objects.first()
        assert entity.name == 'new name'

    def test_model_renaming_different_users_succeeds(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)

        model2 = recipes.model.make(name='test model 2')
        assert model.name == 'my model1'
        assert model2.name == 'test model 2'

        response = client.post(
            '/entities/models/%d/rename' % model.pk,
            data={
                'name': 'test model 2'
            })
        assert response.status_code == 302
        entity = ModelEntity.objects.first()
        assert entity.name == 'test model 2'

    def test_model_renaming_same_users_fails(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)

        model2 = recipes.model.make(author=logged_in_user, name='test model 2')
        assert model.name == 'my model1'
        assert model2.name == 'test model 2'

        response = client.post(
            '/entities/models/%d/rename' % model.pk,
            data={
                'name': 'test model 2'
            })
        assert response.status_code == 200
        entity = ModelEntity.objects.first()
        assert entity.name == 'my model1'

    def test_model_and_protocol_renaming_success(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)

        recipes.protocol.make(author=logged_in_user, name='test protocol')
        assert model.name == 'my model1'

        response = client.post(
            '/entities/models/%d/rename' % model.pk,
            data={
                'name': 'test protocol'
            })
        assert response.status_code == 302
        entity = ModelEntity.objects.first()
        assert entity.name == 'test protocol'

    def test_model_abs_path_the_same(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        helpers.add_version(model, visibility='private')

        abs_path = model.repo_abs_path
        response = client.post(
            '/entities/models/%d/rename' % model.pk,
            data={
                'name': 'test protocol'
            })
        assert response.status_code == 302

        entity = ModelEntity.objects.first()
        assert entity.name == 'test protocol'
        assert abs_path == entity.repo_abs_path


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
class TestEntityDeletionInUseInStory:
    def test_owner_cannot_delete_entity_if_in_use_in_story(
        self, logged_in_user, helpers, client,
        model_with_version, protocol_with_version, story
    ):
        # the presence of in_use (with len>0) will disable the confirm button and add a message in the template
        model_with_version.author = logged_in_user
        model_with_version.save()
        protocol_with_version.author = logged_in_user
        protocol_with_version.save()

        response = client.get('/entities/models/%d/delete' % model_with_version.pk)
        assert 'in_use' in response.context[-1]
        assert str(response.context[-1]['in_use']) == str({(story.id, story.title)})

        response = client.get('/entities/protocols/%d/delete' % protocol_with_version.pk)
        assert 'in_use' in response.context[-1]
        assert str(response.context[-1]['in_use']) == str({(story.id, story.title)})

        # fitting specs are not involved stories
        helpers.add_permission(logged_in_user, 'create_fittingspec')
        fittingspec = recipes.fittingspec.make(author=logged_in_user)
        response = client.get('/fitting/specs/%d/delete' % fittingspec.pk)
        assert 'in_use' in response.context[-1]
        assert len(response.context[-1]['in_use']) == 0


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
        version = model.repocache.latest_version
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, version.sha),
                   version, [])
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   version, [])

        # Now add a second version with tag
        assert model.repocache.versions.count() == 1
        version2 = helpers.add_version(model, visibility='public')
        model.add_tag('my_tag', version2.sha)

        # Commits are yielded newest first
        assert model.repocache.versions.count() == 2
        assert version == model.repocache.versions.last()
        version = model.repocache.latest_version

        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, version.sha),
                   version, ['my_tag'])
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, 'my_tag'),
                   version, ['my_tag'])
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   version, ['my_tag'])

    def test_version_with_two_tags(self, client, helpers):
        model = recipes.model.make()
        helpers.add_version(model, visibility='public')
        version = model.repocache.latest_version
        model.add_tag('tag1', version.sha)
        model.add_tag('tag2', version.sha)

        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, version.sha), version, ['tag1', 'tag2'])
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, 'tag1'), version, ['tag1', 'tag2'])
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, 'tag2'),
                   version, ['tag1', 'tag2'])
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   version, ['tag1', 'tag2'])

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
        populate_entity_cache(model)
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
            protocol1.name: {'required': ['p1r2'], 'optional': ['p1o2']},
            protocol2.name: {'required': ['p2r2'], 'optional': ['p2o2']},
            protocol3.name: {'required': ['p3r1'], 'optional': ['p3o1']},
            protocol4.name: {'required': ['p4r3'], 'optional': ['p4o3']},
        }
        for iface in interfaces:
            assert iface['name'] in expected
            assert iface['required'] == expected[iface['name']]['required']
            assert iface['optional'] == expected[iface['name']]['optional']


@pytest.mark.django_db
class TestModelEntityCompareExperimentsView:
    def test_has_visibility_form(self, client, helpers, public_model):
        response = client.get('/entities/models/%d/versions/%s/compare' %
                              (public_model.pk, public_model.repocache.latest_version.sha))
        assert 'form' in response.context
        assert response.context['form'].initial.get('visibility') == 'public'

    def test_shows_related_experiments(self, client, helpers, experiment_version):
        exp = experiment_version.experiment
        model_version = exp.model.repocache.latest_version
        recipes.experiment_version.make()  # another experiment which should not be included
        exp.model.set_version_visibility('latest', 'public')
        exp.protocol.set_version_visibility('latest', 'public')
        helpers.add_version(exp.protocol, visibility='public')
        # Add an experiment with a newer version of the protocol but that was created earlier
        exp2 = recipes.experiment_version.make(
            experiment__protocol=exp.protocol,
            experiment__protocol_version=exp.protocol.repocache.latest_version,
            experiment__model=exp.model,
            experiment__model_version=model_version,
        ).experiment
        exp2.created_at = exp.created_at - timedelta(seconds=10)
        exp2.save()

        # Add an experiment with a newer version of the protocol and that was created later
        helpers.add_version(exp.protocol, visibility='public')
        exp3 = recipes.experiment_version.make(
            experiment__protocol=exp.protocol,
            experiment__protocol_version=exp.protocol.repocache.latest_version,
            experiment__model=exp.model,
            experiment__model_version=model_version,
        ).experiment

        response = client.get(
            '/entities/models/%d/versions/%s/compare' % (exp.model.pk, model_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [(exp.protocol, [exp3, exp2, exp])]

    def test_applies_visibility(self, client, helpers, experiment_version):
        exp = experiment_version.experiment
        protocol = recipes.protocol.make()
        exp.model.set_version_visibility('latest', 'public')
        exp.protocol.set_version_visibility('latest', 'public')
        protocol_version = helpers.add_version(protocol, visibility='private')
        recipes.runnable.make(
            experiment__protocol=protocol,
            experiment__protocol_version=protocol.repocache.get_version(protocol_version.sha),
            experiment__model=exp.model,
            experiment__model_version=exp.model_version,
        )  # should not be included for visibility reasons

        response = client.get(
            '/entities/models/%d/versions/%s/compare' % (exp.model.pk, exp.model_version.sha)
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
        sha = exp.protocol_version.sha
        model = recipes.model.make()
        exp.protocol.set_version_visibility('latest', 'public')
        exp.model.set_version_visibility('latest', 'public')
        model_version = helpers.add_version(model, visibility='private')
        recipes.experiment_version.make(
            experiment__protocol=exp.protocol,
            experiment__protocol_version=exp.protocol.repocache.get_version(sha),
            experiment__model=model,
            experiment__model_version=model.repocache.get_version(model_version.sha),
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
class TestEntityCompareFittingResultsView:
    def test_has_visibility_form(self, client, helpers, public_model):
        response = client.get('/entities/models/%d/versions/%s/fittings' %
                              (public_model.pk, public_model.repocache.latest_version.sha))
        assert 'form' in response.context
        assert response.context['form'].initial.get('visibility') == 'public'

    def test_shows_fittings_related_to_model_version(self, client, fittingresult_version):
        fit = fittingresult_version.fittingresult

        # should not be included, as it uses a different model and version
        recipes.fittingresult_version.make()

        # should not be included, as it uses a different version of this model
        recipes.fittingresult_version.make(fittingresult__model=fit.model)

        response = client.get(
            '/entities/models/%d/versions/%s/fittings' % (fit.model.pk, fit.model_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [(fit.dataset, [fit])]

    def test_groups_by_dataset_for_model(self, client, public_model):
        model_version = public_model.repocache.latest_version
        dataset1, dataset2 = recipes.dataset.make(_quantity=2, visibility='public')

        # Create publicly visible fitting result versions
        ds1fit1 = recipes.fittingresult_version.make(
            fittingresult__dataset=dataset1,
            fittingresult__model=public_model,
            fittingresult__model_version=model_version,
            fittingresult__protocol_version__visibility='public',
            fittingresult__fittingspec_version__visibility='public',
        ).fittingresult

        ds1fit2 = recipes.fittingresult_version.make(
            fittingresult__dataset=dataset1,
            fittingresult__model=public_model,
            fittingresult__model_version=model_version,
            fittingresult__protocol_version__visibility='public',
            fittingresult__fittingspec_version__visibility='public',
        ).fittingresult

        ds2fit1 = recipes.fittingresult_version.make(
            fittingresult__dataset=dataset2,
            fittingresult__model=public_model,
            fittingresult__model_version=model_version,
            fittingresult__protocol_version__visibility='public',
            fittingresult__fittingspec_version__visibility='public',
        ).fittingresult

        response = client.get(
            '/entities/models/%d/versions/%s/fittings' % (public_model.id, model_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [
            (dataset1, [ds1fit2, ds1fit1]),
            (dataset2, [ds2fit1]),
        ]

    def test_ensure_private_results_are_not_shown_for_model_version(self, client, public_model):
        model_version = public_model.repocache.latest_version
        recipes.fittingresult_version.make(
            fittingresult__model=public_model,
            fittingresult__model_version=model_version,
            fittingresult__protocol_version__visibility='private',
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__dataset__visibility='public'
        )

        recipes.fittingresult_version.make(
            fittingresult__model=public_model,
            fittingresult__model_version=model_version,
            fittingresult__protocol_version__visibility='public',
            fittingresult__fittingspec_version__visibility='private',
            fittingresult__dataset__visibility='public'
        )

        recipes.fittingresult_version.make(
            fittingresult__model=public_model,
            fittingresult__model_version=model_version,
            fittingresult__protocol_version__visibility='public',
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__dataset__visibility='private'
        )

        fit = recipes.fittingresult_version.make(
            fittingresult__model=public_model,
            fittingresult__model_version=model_version,
            fittingresult__protocol_version__visibility='public',
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__dataset__visibility='public'
        ).fittingresult

        response = client.get(
            '/entities/models/%d/versions/%s/fittings' % (public_model.id, model_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [
            (fit.dataset, [fit]),
        ]

    def test_shows_fittings_related_to_protocol_version(self, client, fittingresult_version):
        fit = fittingresult_version.fittingresult

        # should not be included, as it uses a different protocol
        recipes.fittingresult_version.make()

        # should not be included, as it uses a different version of this protocol
        recipes.fittingresult_version.make(fittingresult__protocol=fit.protocol)

        response = client.get(
            '/entities/protocols/%d/versions/%s/fittings' % (fit.protocol.pk, fit.protocol_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [(fit.dataset, [(fit.model, [fit])])]

    def test_groups_by_dataset_for_protocol(self, client, helpers, public_protocol):
        protocol_version = public_protocol.repocache.latest_version
        ds1, ds2 = recipes.dataset.make(_quantity=2, visibility='public')
        m1, m2 = recipes.model.make(_quantity=2)
        m1v = helpers.add_cached_version(m1, visibility='public')
        m2v = helpers.add_cached_version(m2, visibility='public')

        # Create publicly visible fitting result versions
        fit1_ds1_m1 = recipes.fittingresult_version.make(
            fittingresult__dataset=ds1,
            fittingresult__protocol=public_protocol,
            fittingresult__protocol_version=protocol_version,
            fittingresult__model=m1,
            fittingresult__model_version=m1v,
            fittingresult__fittingspec_version__visibility='public',
        ).fittingresult

        fit2_ds1_m2 = recipes.fittingresult_version.make(
            fittingresult__dataset=ds1,
            fittingresult__protocol=public_protocol,
            fittingresult__protocol_version=protocol_version,
            fittingresult__model=m2,
            fittingresult__model_version=m2v,
            fittingresult__fittingspec_version__visibility='public',
        ).fittingresult

        fit3_ds2_m1 = recipes.fittingresult_version.make(
            fittingresult__dataset=ds2,
            fittingresult__protocol=public_protocol,
            fittingresult__protocol_version=protocol_version,
            fittingresult__model=m1,
            fittingresult__model_version=m1v,
            fittingresult__fittingspec_version__visibility='public',
        ).fittingresult

        response = client.get(
            '/entities/protocols/%d/versions/%s/fittings' % (public_protocol.id, protocol_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [
            (ds1, [
                (m1, [fit1_ds1_m1]),
                (m2, [fit2_ds1_m2]),
            ]),
            (ds2, [
                (m1, [fit3_ds2_m1]),
            ]),
        ]

    def test_multiple_model_versions_for_protocol_version(self, client, helpers, public_protocol, public_dataset):
        protocol_version = public_protocol.repocache.latest_version
        m1, m2 = recipes.model.make(_quantity=2)
        m1v1 = helpers.add_cached_version(m1, visibility='public')
        m1v2 = helpers.add_cached_version(m1, visibility='public')
        m2v = helpers.add_cached_version(m2, visibility='public')

        # Create publicly visible fitting result versions
        fit1_m1v1 = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__protocol=public_protocol,
            fittingresult__protocol_version=protocol_version,
            fittingresult__model=m1,
            fittingresult__model_version=m1v1,
            fittingresult__fittingspec_version__visibility='public',
        ).fittingresult

        fit2_m1v2 = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__protocol=public_protocol,
            fittingresult__protocol_version=protocol_version,
            fittingresult__model=m1,
            fittingresult__model_version=m1v2,
            fittingresult__fittingspec_version__visibility='public',
        ).fittingresult

        fit3_m2v = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__protocol=public_protocol,
            fittingresult__protocol_version=protocol_version,
            fittingresult__model=m2,
            fittingresult__model_version=m2v,
            fittingresult__fittingspec_version__visibility='public',
        ).fittingresult

        response = client.get(
            '/entities/protocols/%d/versions/%s/fittings' % (public_protocol.id, protocol_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [
            (public_dataset, [
                (m1, [fit2_m1v2, fit1_m1v1]),
                (m2, [fit3_m2v]),
            ]),
        ]

    def test_ensure_private_results_are_not_shown_for_protocol_version(self, client, public_protocol):
        protocol_version = public_protocol.repocache.latest_version

        recipes.fittingresult_version.make(
            fittingresult__protocol=public_protocol,
            fittingresult__protocol_version=protocol_version,
            fittingresult__model_version__visibility='private',
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__dataset__visibility='public'
        )

        recipes.fittingresult_version.make(
            fittingresult__protocol=public_protocol,
            fittingresult__protocol_version=protocol_version,
            fittingresult__model_version__visibility='public',
            fittingresult__fittingspec_version__visibility='private',
            fittingresult__dataset__visibility='public'
        )

        recipes.fittingresult_version.make(
            fittingresult__protocol=public_protocol,
            fittingresult__protocol_version=protocol_version,
            fittingresult__model_version__visibility='public',
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__dataset__visibility='private'
        )

        fit = recipes.fittingresult_version.make(
            fittingresult__protocol=public_protocol,
            fittingresult__protocol_version=protocol_version,
            fittingresult__model_version__visibility='public',
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__dataset__visibility='public'
        ).fittingresult

        response = client.get(
            '/entities/protocols/%d/versions/%s/fittings' % (public_protocol.id, protocol_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [
            (fit.dataset, [(fit.model, [fit])]),
        ]

    def test_shows_fittings_related_to_fittingspec_version(self, client, fittingresult_version):
        fit = fittingresult_version.fittingresult

        # should not be included, as it uses a different fittingspec
        recipes.fittingresult_version.make()

        # should not be included, as it uses a different version of this fittingspec
        recipes.fittingresult_version.make(fittingresult__fittingspec=fit.fittingspec)

        response = client.get(
            '/fitting/specs/%d/versions/%s/fittings' % (fit.fittingspec.pk, fit.fittingspec_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [(fit.dataset, [(fit.model, [fit])])]

    def test_groups_by_dataset_for_fittingspec(self, client, helpers, public_fittingspec):
        fittingspec_version = public_fittingspec.repocache.latest_version
        ds1, ds2 = recipes.dataset.make(_quantity=2, visibility='public')
        m1, m2 = recipes.model.make(_quantity=2)
        m1v = helpers.add_cached_version(m1, visibility='public')
        m2v = helpers.add_cached_version(m2, visibility='public')

        # Create publicly visible fitting result versions
        fit1_ds1_m1 = recipes.fittingresult_version.make(
            fittingresult__dataset=ds1,
            fittingresult__fittingspec=public_fittingspec,
            fittingresult__fittingspec_version=fittingspec_version,
            fittingresult__model=m1,
            fittingresult__model_version=m1v,
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        fit2_ds1_m2 = recipes.fittingresult_version.make(
            fittingresult__dataset=ds1,
            fittingresult__fittingspec=public_fittingspec,
            fittingresult__fittingspec_version=fittingspec_version,
            fittingresult__model=m2,
            fittingresult__model_version=m2v,
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        fit3_ds2_m1 = recipes.fittingresult_version.make(
            fittingresult__dataset=ds2,
            fittingresult__fittingspec=public_fittingspec,
            fittingresult__fittingspec_version=fittingspec_version,
            fittingresult__model=m1,
            fittingresult__model_version=m1v,
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        response = client.get(
            '/fitting/specs/%d/versions/%s/fittings' % (public_fittingspec.id, fittingspec_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [
            (ds1, [
                (m1, [fit1_ds1_m1]),
                (m2, [fit2_ds1_m2]),
            ]),
            (ds2, [
                (m1, [fit3_ds2_m1]),
            ]),
        ]

    def test_multiple_model_versions_for_fittingspec_version(self, client, helpers, public_fittingspec, public_dataset):
        fittingspec_version = public_fittingspec.repocache.latest_version
        m1, m2 = recipes.model.make(_quantity=2)
        m1v1 = helpers.add_cached_version(m1, visibility='public')
        m1v2 = helpers.add_cached_version(m1, visibility='public')
        m2v = helpers.add_cached_version(m2, visibility='public')

        # Create publicly visible fitting result versions
        fit1_m1v1 = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__fittingspec=public_fittingspec,
            fittingresult__fittingspec_version=fittingspec_version,
            fittingresult__model=m1,
            fittingresult__model_version=m1v1,
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        fit2_m1v2 = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__fittingspec=public_fittingspec,
            fittingresult__fittingspec_version=fittingspec_version,
            fittingresult__model=m1,
            fittingresult__model_version=m1v2,
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        fit3_m2v = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__fittingspec=public_fittingspec,
            fittingresult__fittingspec_version=fittingspec_version,
            fittingresult__model=m2,
            fittingresult__model_version=m2v,
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        response = client.get(
            '/fitting/specs/%d/versions/%s/fittings' % (public_fittingspec.id, fittingspec_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [
            (public_dataset, [
                (m1, [fit2_m1v2, fit1_m1v1]),
                (m2, [fit3_m2v]),
            ]),
        ]

    def test_ensure_private_results_are_not_shown_for_fittingspec_version(self, client, public_fittingspec):
        fittingspec_version = public_fittingspec.repocache.latest_version

        recipes.fittingresult_version.make(
            fittingresult__fittingspec=public_fittingspec,
            fittingresult__fittingspec_version=fittingspec_version,
            fittingresult__model_version__visibility='private',
            fittingresult__protocol_version__visibility='public',
            fittingresult__dataset__visibility='public'
        )

        recipes.fittingresult_version.make(
            fittingresult__fittingspec=public_fittingspec,
            fittingresult__fittingspec_version=fittingspec_version,
            fittingresult__model_version__visibility='public',
            fittingresult__protocol_version__visibility='private',
            fittingresult__dataset__visibility='public'
        )

        recipes.fittingresult_version.make(
            fittingresult__fittingspec=public_fittingspec,
            fittingresult__fittingspec_version=fittingspec_version,
            fittingresult__model_version__visibility='public',
            fittingresult__protocol_version__visibility='public',
            fittingresult__dataset__visibility='private'
        )

        fit = recipes.fittingresult_version.make(
            fittingresult__fittingspec=public_fittingspec,
            fittingresult__fittingspec_version=fittingspec_version,
            fittingresult__model_version__visibility='public',
            fittingresult__protocol_version__visibility='public',
            fittingresult__dataset__visibility='public'
        ).fittingresult

        response = client.get(
            '/fitting/specs/%d/versions/%s/fittings' % (public_fittingspec.id, fittingspec_version.sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [
            (fit.dataset, [(fit.model, [fit])]),
        ]


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

    def test_invalid_tag(self, logged_in_user, client, helpers):
        model = recipes.model.make(author=logged_in_user)
        helpers.add_permission(logged_in_user, 'create_model')
        helpers.add_version(model)
        commit = model.repo.latest_commit

        response = client.post(
            '/entities/tag/%d/%s' % (model.pk, commit.sha),
            data={
                'tag': '/invalid tag',
            },
        )
        assert response.status_code == 200
        assert "Please enter a valid tag name" in response.rendered_content

    def test_cannot_tag_as_non_owner(self, logged_in_user, client, helpers):
        protocol = recipes.protocol.make()
        commit = helpers.add_version(protocol)
        response = client.post(
            '/entities/tag/%d/%s' % (protocol.pk, commit.sha),
            data={},
        )
        assert response.status_code == 403

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
            (['v1'], model.repocache.get_version(commit2.sha)),
            ([], model.repocache.get_version(commit1.sha)),
        ]

    def test_only_shows_visible_versions(self, client, helpers):
        model = recipes.model.make()
        helpers.add_fake_version(model, visibility='private')
        commit2 = helpers.add_fake_version(model, visibility='public')
        helpers.add_fake_version(model, visibility='private')

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
class TestTransfer:
    def test_transfer_success(self, client, logged_in_user, other_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        commit = helpers.add_version(model, visibility='public')
        oldpath = model.repo_abs_path

        assert model.author.email == 'test@example.com'
        response = client.post(
            '/entities/models/%d/transfer' % model.pk,
            data={
                'email': other_user.email,
            },
        )
        assert response.status_code == 302
        model.refresh_from_db()
        assert model.author == other_user
        assert not oldpath.exists()
        assert model.repo_abs_path.exists()
        assert model.repocache.latest_version.sha == commit.sha

    def test_transfer_invalid_user(self, client, logged_in_user, other_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')

        model = recipes.model.make(author=logged_in_user)
        commit = helpers.add_version(model, visibility='public')

        assert model.author.email == 'test@example.com'
        response = client.post(
            '/entities/models/%d/transfer' % model.pk,
            data={
                'email': 'invalid@example.com',
            },
        )
        assert response.status_code == 200
        model.refresh_from_db()
        assert model.author == logged_in_user
        assert model.repocache.latest_version.sha == commit.sha

    def test_transfer_other_user_has_same_named_entity(self, client, logged_in_user, other_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        commit = helpers.add_version(model, visibility='public')

        other_model = recipes.model.make(author=other_user)
        other_model.name = model.name
        other_model.save()

        assert model.author.email == 'test@example.com'
        response = client.post(
            '/entities/models/%d/transfer' % model.pk,
            data={
                'email': 'other@example.com',
            },
        )
        assert response.status_code == 200
        model.refresh_from_db()
        assert model.author == logged_in_user
        assert model.repocache.latest_version.sha == commit.sha


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
                'parent_hexsha': model.repo.latest_commit.sha,
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
                'parent_hexsha': model.repo.latest_commit.sha,
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
                'parent_hexsha': model.repo.latest_commit.sha,
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

    def test_new_model_version_existing_story(self, client, logged_in_user, helpers, story):
        assert len(mail.outbox) == 0
        graph = StoryGraph.objects.get(story=story)
        assert not story.email_sent
        assert graph.protocol_is_latest
        assert graph.all_model_versions_latest
        assert not graph.email_sent
        helpers.add_permission(logged_in_user, 'create_model')

        model = graph.Cachedmodelversions.first().model
        helpers.add_version(model,
                            filename='file1.txt',
                            tag_name=None,
                            visibility=None,
                            cache=True,
                            message='file',
                            contents='entity contents')

        story.refresh_from_db()
        graph.refresh_from_db()
        assert story.email_sent
        assert graph.protocol_is_latest
        assert not graph.all_model_versions_latest
        assert graph.email_sent
        assert len(mail.outbox) == 1

    def test_cannot_create_model_version_as_non_owner(self, logged_in_user, client):
        model = recipes.model.make()
        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={},
        )
        assert response.status_code == 403

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
        assert CachedProtocolVersion.README_NAME in commit.filenames
        readme = commit.get_blob(CachedProtocolVersion.README_NAME)
        assert readme.data_stream.read() == doc
        # Check new version analysis "happened"
        assert mock_check.called
        mock_check.assert_called_once_with(protocol, commit.sha)

        assert 0 == PlannedExperiment.objects.count()
        assert 0 == protocol.files.count()

    @patch('requests.post')
    def test_re_analyses_for_new_interface_info(self, mock_post, protocol_with_version, helpers):
        version = protocol_with_version.repocache.latest_version
        # Pretend the version was analysed with the old code (just checking model interface)
        terms = [
            ProtocolInterface(protocol_version=version, term='optional', optional=True),
            ProtocolInterface(protocol_version=version, term='required', optional=False),
        ]
        ProtocolInterface.objects.bulk_create(terms)
        assert not version.ioputs.exists()
        assert not version.has_readme
        assert not AnalysisTask.objects.exists()
        # Pretend we added a readme before (and have a main file to parse)
        protocol_with_version.repo.latest_commit.add_ephemeral_file(version.README_NAME, b'fake readme')
        version.master_filename = version.README_NAME
        version.save()
        # Run the analysis
        mock_post.return_value.content = b''
        protocol_with_version.analyse_new_version(version)
        # Check an analysis would run
        version.refresh_from_db()
        assert mock_post.called
        assert AnalysisTask.objects.exists()
        assert not version.ioputs.exists()  # We didn't actually submit an analysis task
        assert version.has_readme  # Because we added a readme before

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
        assert CachedProtocolVersion.README_NAME in commit.filenames
        readme = commit.get_blob(CachedProtocolVersion.README_NAME)
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
        assert response.status_code == 403

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

    def test_invalid_tag(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)

        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'filename[]': '',
                'commit_message': 'first commit',
                'tag': '/invalid tag',
                'visibility': 'public',
            },
        )
        assert response.status_code == 200
        assert "Please enter a valid tag name" in response.rendered_content

    @pytest.mark.parametrize("route", ['main_form', 'edit_file'])
    def test_rerun_experiments(self, logged_in_user, other_user, client, helpers, route):
        # Set up previous experiments
        m1 = recipes.model.make(author=logged_in_user)
        m1v1 = helpers.add_version(m1, visibility='private')
        m1v2 = helpers.add_version(m1, visibility='private')

        m2 = recipes.model.make(author=other_user)
        m2v1 = helpers.add_version(m2, visibility='public')

        def _add_experiment(proto_author, proto_vis, shared=False,
                            proto=None, proto_commit=None,
                            model=m1, model_commit=m1v1):
            if proto is None:
                proto = recipes.protocol.make(author=proto_author)
                proto_commit = helpers.add_version(proto, visibility=proto_vis)
            recipes.experiment_version.make(
                status='SUCCESS',
                experiment__model=model,
                experiment__model_version=model.repocache.get_version(model_commit.sha),
                experiment__protocol=proto,
                experiment__protocol_version=proto.repocache.get_version(proto_commit.sha),
            )
            if shared:
                assign_perm('edit_entity', logged_in_user, proto)
            return proto

        p1 = _add_experiment(logged_in_user, 'private', model=m1, model_commit=m1v2)
        p1v2 = helpers.add_version(p1, visibility='private')
        _add_experiment(logged_in_user, 'private', model=m1, model_commit=m1v1, proto=p1, proto_commit=p1v2)
        _add_experiment(logged_in_user, 'private', model=m2, model_commit=m2v1, proto=p1, proto_commit=p1v2)
        _add_experiment(logged_in_user, 'public', model=m2, model_commit=m2v1)
        p3 = _add_experiment(other_user, 'public', model=m1, model_commit=m1v2)
        p3v1 = p3.repocache.latest_version
        p3v2 = helpers.add_version(p3, visibility='private')
        _add_experiment(logged_in_user, 'private', model=m1, model_commit=m1v2, proto=p3, proto_commit=p3v2)
        p4 = _add_experiment(other_user, 'public', model=m1, model_commit=m1v2, shared=True)
        p4v2 = helpers.add_version(p4, visibility='private')
        _add_experiment(other_user, 'private', model=m1, model_commit=m1v2)

        # Create a new version of our model, re-running experiments
        helpers.add_permission(logged_in_user, 'create_model')
        if route == 'main_form':
            recipes.model_file.make(
                entity=m1,
                upload=SimpleUploadedFile('file2.txt', b'file 2'),
                original_name='file2.txt',
            )
            response = client.post(
                '/entities/models/%d/versions/new' % m1.pk,
                data={
                    'parent_hexsha': m1.repo.latest_commit.sha,
                    'filename[]': ['uploads/file2.txt'],
                    'mainEntry': ['file2.txt'],
                    'commit_message': 'new',
                    'visibility': 'private',
                    'tag': '',
                    'rerun_expts': '1',
                },
            )
            assert response.status_code == 302
            new_commit = m1.repo.latest_commit
            assert response.url == '/entities/models/%d/versions/%s' % (m1.id, new_commit.sha)
        else:
            assert route == 'edit_file'
            response = client.post('/entities/models/%d/versions/edit' % m1.id, json.dumps({
                'parent_hexsha': m1v2.sha,
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
            new_commit = m1.repo.latest_commit
            assert detail['updateEntityFile']['url'] == '/entities/models/%d/versions/%s' % (
                m1.id, new_commit.sha)

        # Test that planned experiments have been added correctly
        expected_proto_versions = set([
            (p1, p1v2.sha),
            (p3, p3v1.sha),
            (p4, p4v2.sha),
        ])
        assert len(expected_proto_versions) == PlannedExperiment.objects.count()
        for planned_experiment in PlannedExperiment.objects.all():
            assert planned_experiment.submitter == logged_in_user
            assert planned_experiment.model == m1
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
        assert response.status_code == 403

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
        assert not version.ioputs.exists()
        assert not protocol.is_parsed_ok(version)

        # Submit the fake task response
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': task_id,
            'returntype': 'success',
            'required': [],
            'optional': [],
            'ioputs': [],
        }), content_type='application/json')
        assert response.status_code == 200

        # Check the analysis task has been deleted
        assert not AnalysisTask.objects.filter(id=task_id).exists()

        # Check there is an analysed flag, and nothing else
        assert version.interface.count() == 0
        assert version.ioputs.count() == 1
        flag = version.ioputs.get()
        assert flag.kind == ProtocolIoputs.FLAG

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
        assert not version.ioputs.exists()
        assert not protocol.is_parsed_ok(version)

        # Submit the fake task response
        req = ['r1', 'r2']
        opt = ['o1']
        io = [  # You can have an input & output with the same name
            {'name': 'n', 'units': 'u', 'kind': 'output'},
            {'name': 'n', 'units': 'u', 'kind': 'input'},
        ]
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': task_id,
            'returntype': 'success',
            'required': req,
            'optional': opt,
            'ioputs': io,
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
        assert version.ioputs.count() == len(io) + 1
        for item in io:
            kind = ProtocolIoputs.INPUT if item['kind'] == 'input' else ProtocolIoputs.OUTPUT
            db_item = version.ioputs.get(name=item['name'], kind=kind)
            assert db_item.units == item['units']
        assert version.ioputs.filter(kind=ProtocolIoputs.FLAG).count() == 1

    def test_re_analysis_with_protocol_outputs(self, client, analysis_task):
        task_id = str(analysis_task.id)
        protocol = analysis_task.entity
        hexsha = analysis_task.version
        version = protocol.repocache.get_version(hexsha)

        # Set up interface as stored by original analysis
        ProtocolInterface(protocol_version=version, term='old_req', optional=False).save()
        ProtocolInterface(protocol_version=version, term='old_opt', optional=True).save()
        version.parsed_ok = True
        version.save()
        assert version.interface.exists()
        assert not version.ioputs.exists()
        assert protocol.is_parsed_ok(version)

        # Submit the fake task response
        req = ['r1', 'r2']
        opt = ['o1']
        io = [  # You can have an input & output with the same name
            {'name': 'n', 'units': 'u', 'kind': 'output'},
            {'name': 'n', 'units': 'u', 'kind': 'input'},
        ]
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': task_id,
            'returntype': 'success',
            'required': req,
            'optional': opt,
            'ioputs': io,
        }), content_type='application/json')
        assert response.status_code == 200
        assert response.json() == {}

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
        assert version.ioputs.count() == len(io) + 1
        for item in io:
            kind = ProtocolIoputs.INPUT if item['kind'] == 'input' else ProtocolIoputs.OUTPUT
            db_item = version.ioputs.get(name=item['name'], kind=kind)
            assert db_item.units == item['units']
        assert version.ioputs.filter(kind=ProtocolIoputs.FLAG).count() == 1

    @patch('requests.post')
    def test_stores_error_response(self, mock_post, client, analysis_task):
        task_id = str(analysis_task.id)
        protocol = analysis_task.entity
        hexsha = analysis_task.version
        version = protocol.repocache.get_version(hexsha)

        # Check there is no interface or error file initially
        assert not version.interface.exists()
        assert not version.ioputs.exists()
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
            'ioputs': [],
        }), content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['error'].startswith('duplicate term provided: ')

    def test_errors_on_duplicate_outputs(self, client, analysis_task):
        # Submit the fake task response
        io = [
            {'name': 'o', 'units': 'u', 'kind': 'output'},
            {'name': 'o', 'units': 'u', 'kind': 'output'},
        ]
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': str(analysis_task.id),
            'returntype': 'success',
            'required': [],
            'optional': [],
            'ioputs': io,
        }), content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['error'].startswith('duplicate input or output provided: ')

    def test_errors_on_duplicate_inputs(self, client, analysis_task):
        # Submit the fake task response
        io = [
            {'name': 'o', 'units': 'u', 'kind': 'input'},
            {'name': 'o', 'units': 'u', 'kind': 'input'},
        ]
        response = client.post('/entities/callback/check-proto', json.dumps({
            'signature': str(analysis_task.id),
            'returntype': 'success',
            'required': [],
            'optional': [],
            'ioputs': io,
        }), content_type='application/json')
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert data['error'].startswith('duplicate input or output provided: ')

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
            'attachment; filename=%s_%s.zip' % (model.name.replace(' ', '_'), commit.sha)
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

    @pytest.mark.parametrize("entity_type,url_fragment", [
        ('model', '/entities/models'),
        ('protocol', '/entities/protocols'),
        ('fittingspec', '/fitting/specs'),
    ])
    def test_anonymous_entity_download_for_running_fittingresult(
        self, client, queued_fittingresult, entity_type, url_fragment
    ):
        entity = getattr(queued_fittingresult.fittingresult, entity_type)
        sha = entity.repo.latest_commit.sha
        entity.set_version_visibility(sha, 'private')

        response = client.get(
            '%s/%d/versions/latest/archive' % (url_fragment, entity.pk),
            HTTP_AUTHORIZATION='Token {}'.format(queued_fittingresult.signature)
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

        version1 = protocol.repocache.get_version(commit1.sha)
        version2 = protocol.repocache.get_version(commit2.sha)

        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, 'latest'))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'entity': protocol,
                                                    'name': protocol.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
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

        version1 = protocol.repocache.get_version(commit1.sha)
        version2 = protocol.repocache.get_version(commit2.sha)

        other_version1 = other_protocol.repocache.get_version(other_commit1.sha)
        other_version2 = other_protocol.repocache.get_version(other_commit2.sha)

        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, 'latest'))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'entity': protocol,
                                                    'name': protocol.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['other_object_list'] == [
            {'id': other_protocol.pk,
             'entity': other_protocol,
             'name': other_protocol.name,
             'versions': [{'commit': other_version2, 'tags': ['v1'], 'latest': True},
                          {'commit': other_version1, 'tags': [], 'latest': False}]},
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

        version1 = protocol.repocache.get_version(commit1.sha)
        version2 = protocol.repocache.get_version(commit2.sha)

        # Test context has correct information
        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'entity': protocol,
                                                    'name': protocol.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
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

        version1 = protocol.repocache.get_version(commit1.sha)
        version2 = protocol.repocache.get_version(commit2.sha)

        recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=model,
            experiment__model_version=model.repocache.get_version(commit_model.sha),
            experiment__protocol=protocol,
            experiment__protocol_version=protocol.repocache.get_version(commit1.sha),)

        # Test context has correct information
        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'entity': protocol,
                                                    'name': protocol.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
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

        version1 = protocol.repocache.get_version(commit1.sha)
        version2 = protocol.repocache.get_version(commit2.sha)

        other_version1 = other_protocol.repocache.get_version(other_commit1.sha)
        other_version2 = other_protocol.repocache.get_version(other_commit2.sha)

        # check context
        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'entity': protocol,
                                                    'name': protocol.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['other_object_list'] == [
            {'id': other_protocol.pk,
             'entity': other_protocol,
             'name': other_protocol.name,
             'versions': [{'commit': other_version2, 'tags': ['v1'], 'latest': True},
                          {'commit': other_version1, 'tags': [], 'latest': False}]},
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

        version1 = protocol.repocache.get_version(commit1.sha)
        version2 = protocol.repocache.get_version(commit2.sha)

        # display page using tag
        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, 'model_v1'))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'entity': protocol,
                                                    'name': protocol.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
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

        version1 = model.repocache.get_version(commit1.sha)
        version2 = model.repocache.get_version(commit2.sha)

        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, 'latest'))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'entity': model,
                                                    'name': model.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
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

        version1 = model.repocache.get_version(commit1.sha)
        version2 = model.repocache.get_version(commit2.sha)

        other_version1 = other_model.repocache.get_version(other_commit1.sha)
        other_version2 = other_model.repocache.get_version(other_commit2.sha)

        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, 'latest'))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'entity': model,
                                                    'name': model.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['other_object_list'] == [
            {'id': other_model.pk,
             'entity': other_model,
             'name': other_model.name,
             'versions': [{'commit': other_version2, 'tags': ['v1'], 'latest': True},
                          {'commit': other_version1, 'tags': [], 'latest': False}]},
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

        version1 = model.repocache.get_version(commit1.sha)
        version2 = model.repocache.get_version(commit2.sha)

        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, commit_protocol.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'entity': model,
                                                    'name': model.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
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
            experiment__model_version=model.repocache.get_version(commit1.sha),
            experiment__protocol=protocol,
            experiment__protocol_version=protocol.repocache.get_version(commit_protocol.sha))
        # This experiment has no versions so should not be excluded
        recipes.experiment.make(
            model=model,
            model_version=model.repocache.get_version(commit2.sha),
            protocol=protocol,
            protocol_version=protocol.repocache.get_version(commit_protocol.sha))

        version1 = model.repocache.get_version(commit1.sha)
        version2 = model.repocache.get_version(commit2.sha)

        # Test context has correct information
        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, commit_protocol.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'entity': model,
                                                    'name': model.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
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

        version1 = model.repocache.get_version(commit1.sha)
        version2 = model.repocache.get_version(commit2.sha)
        other_version1 = other_model.repocache.get_version(other_commit1.sha)
        other_version2 = other_model.repocache.get_version(other_commit2.sha)

        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, commit_protocol.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'entity': model,
                                                    'name': model.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
                                                   ]
        assert response.context['other_object_list'] == [
            {'id': other_model.pk,
             'entity': other_model,
             'name': other_model.name,
             'versions': [{'commit': other_version2, 'tags': ['v1'], 'latest': True},
                          {'commit': other_version1, 'tags': [], 'latest': False}]},
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

        version1 = protocol.repocache.get_version(commit1.sha)
        version2 = protocol.repocache.get_version(commit2.sha)

        # Test context has correct information
        response = client.get(
            '/entities/models/%d/versions/%s/runexperiments' % (model.pk, commit_model.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': protocol.pk,
                                                    'entity': protocol,
                                                    'name': protocol.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
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

        version1 = model.repocache.get_version(commit1.sha)
        version2 = model.repocache.get_version(commit2.sha)

        # display using sha
        response = client.get(
            '/entities/protocols/%d/versions/%s/runexperiments' % (protocol.pk, proto_commit1.sha))
        assert response.status_code == 200
        assert response.context['object_list'] == [{'id': model.pk,
                                                    'entity': model,
                                                    'name': model.name,
                                                    'versions': [{'commit': version2, 'tags': ['v1'], 'latest': True},
                                                                 {'commit': version1, 'tags': [], 'latest': False}]},
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


@pytest.mark.django_db
class TestModelGroupViews:
    def test_create_modelgroup(self, logged_in_user, client, helpers):
        assert ModelGroup.objects.count() == 0
        helpers.add_permission(logged_in_user, 'create_model')

        assert ModelGroup.objects.count() == 0
        model = recipes.model.make(author=logged_in_user)
        response = client.post('/entities/modelgroups/new', data={
            'title': 'mymodelgroup',
            'visibility': 'private',
            'models': model.pk,
        })
        assert response.status_code == 302
        assert ModelGroup.objects.count() == 1
        modelgroup = ModelGroup.objects.first()
        assert modelgroup.title == 'mymodelgroup'
        assert modelgroup.visibility == 'private'
        assert list(modelgroup.models.all()) == [model]

    def test_create_modelgroup_with_same_name(self, logged_in_user, other_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        helpers.add_permission(other_user, 'create_model')

        model = recipes.model.make(author=logged_in_user)
        recipes.modelgroup.make(author=logged_in_user, title='mymodelgroup')

        # can't create duplicate model for author
        response = client.post('/entities/modelgroups/new', data={
            'title': 'mymodelgroup',
            'visibility': 'private',
            'models': model.pk,
        })
        assert response.status_code == 200
        assert ModelGroup.objects.count() == 1

        helpers.login(client, other_user)
        model.add_collaborator(other_user)
        # can create duplicate model for another author
        response = client.post('/entities/modelgroups/new', data={
            'title': 'mymodelgroup',
            'visibility': 'private',
            'models': model.pk,
        })
        assert response.status_code == 302
        assert ModelGroup.objects.count() == 2

    def test_create_modelgroup_requires_permissions(self, logged_in_user, client):
        response = client.post(
            '/entities/modelgroups/new',
            data={},
        )
        assert response.status_code == 403

    def test_cannot_edit_modelgroup_without_edit_permission(self, logged_in_user, other_user, client):
        modelgroup = recipes.modelgroup.make(author=other_user, title='mg', visibility='private')
        model = recipes.model.make(author=other_user)

        assign_perm('edit_entity', logged_in_user, model)

        response = client.post('/entities/modelgroups/%s/' % modelgroup.pk, data={
            'id': modelgroup.pk,
            'title': 'mymodelgroup',
            'visibility': 'private',
            'models': model.pk,
        })
        assert response.status_code == 404
        assert ModelGroup.objects.count() == 1

        assert ModelGroup.objects.first().title == 'mg'
        assert ModelGroup.objects.first().visibility == 'private'
        assert len(ModelGroup.objects.first().models.all()) == 0

        assign_perm('edit_entity', logged_in_user, model)
        assign_perm('edit_modelgroup', logged_in_user, modelgroup)
        response = client.post('/entities/modelgroups/%s' % modelgroup.pk, data={
            'title': 'new title',
            'visibility': 'private',
            'models': model.pk,
        })
        assert response.status_code == 302
        assert ModelGroup.objects.count() == 1
        assert ModelGroup.objects.first().title == 'new title'
        assert ModelGroup.objects.first().visibility == 'private'
        assert list(ModelGroup.objects.first().models.all()) == [model]

    def test_delete_modelgroup(self, logged_in_user, other_user, client):
        modelgroup = recipes.modelgroup.make(author=other_user)
        modelgroup2 = recipes.modelgroup.make(author=logged_in_user)
        assert ModelGroup.objects.count() == 2

        # cannot delete modelgroup you don't have access to
        response = client.post('/entities/modelgroups/%s/delete' % modelgroup.pk, data={})
        assert response.status_code == 403
        assert ModelGroup.objects.count() == 2

        # can delete own model group
        response = client.post('/entities/modelgroups/%s/delete' % modelgroup2.pk, data={})
        assert response.status_code == 302
        assert ModelGroup.objects.count() == 1

    def test_collaborator(self, logged_in_user, other_user, client):
        modelgroup = recipes.modelgroup.make(author=logged_in_user)
        assert ModelGroup.objects.count() == 1
        assert ModelGroup.objects.first().collaborators == []

        response = client.post('/entities/modelgroups/%s/collaborators' % modelgroup.pk,
                               data={'form-0-email': other_user.email,
                                     'form-MAX_NUM_FORMS': 1000,
                                     'form-0-DELETE': '',
                                     'form-INITIAL_FORMS': 0,
                                     'form-MIN_NUM_FORMS': 0,
                                     'form-TOTAL_FORMS': 1,
                                     })
        assert response.status_code == 302
        assert ModelGroup.objects.count() == 1
        assert ModelGroup.objects.first().collaborators == [other_user]

    def test_transfer_owner(self, logged_in_user, other_user, client):
        modelgroup = recipes.modelgroup.make(author=logged_in_user)
        assert ModelGroup.objects.count() == 1
        assert ModelGroup.objects.first().author == logged_in_user

        response = client.post('/entities/modelgroups/%s/transfer' % modelgroup.pk,
                               data={'email': other_user.email})
        assert response.status_code == 302
        assert ModelGroup.objects.count() == 1
        assert ModelGroup.objects.first().author == other_user

    def test_transfer_invalid_other_user(self, logged_in_user, client):
        modelgroup = recipes.modelgroup.make(author=logged_in_user)
        assert ModelGroup.objects.count() == 1
        assert ModelGroup.objects.first().author == logged_in_user

        response = client.post('/entities/modelgroups/%s/transfer' % modelgroup.pk,
                               data={'email': 'users.does.not@exist.com'})
        assert response.status_code == 200
        assert ModelGroup.objects.count() == 1
        assert ModelGroup.objects.first().author == logged_in_user

    def test_cannot_transfer_if_user_has_model_with_name(self, logged_in_user,
                                                         other_user, client):
        recipes.modelgroup.make(author=other_user, title='my modelgroup')
        modelgroup = recipes.modelgroup.make(author=logged_in_user, title='my modelgroup')
        assert ModelGroup.objects.count() == 2
        assert set([m.author for m in ModelGroup.objects.all()]) == {logged_in_user, other_user}

        response = client.post('/entities/modelgroups/%s/transfer' % modelgroup.pk,
                               data={'email': other_user.email})
        assert response.status_code == 200
        assert ModelGroup.objects.count() == 2
        assert set([m.author for m in ModelGroup.objects.all()]) == {logged_in_user, other_user}

    def test_modelgroup_list_not_logged_in(self, user, client):
        recipes.modelgroup.make(author=user, _quantity=2)
        response = client.get('/entities/modelgroups/')
        assert response.status_code == 302
        assert 'login' in response.url

    def test_modelgroup_list_logged_in(self, logged_in_user, client):
        modelgroups = recipes.modelgroup.make(author=logged_in_user, _quantity=2)
        response = client.get('/entities/modelgroups/')
        assert response.status_code == 200
        assert list(response.context_data['modelgroup_list'].all()) == modelgroups
