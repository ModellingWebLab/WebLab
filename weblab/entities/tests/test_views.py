import io
import json
import zipfile
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.dateparse import parse_datetime
from guardian.shortcuts import assign_perm

from core import recipes
from entities.models import Entity, ModelEntity, ProtocolEntity


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
        assert Entity.objects.filter(pk=entity.pk).exists()
        assert repo_path.exists()

        response = client.post(url % entity.pk)

        assert response.status_code == 302
        assert response.url == list_url

        assert not Entity.objects.filter(pk=entity.pk).exists()
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
        assert Entity.objects.filter(pk=entity.pk).exists()
        assert repo_path.exists()


@pytest.mark.django_db
class TestEntityDetail:
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
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, commit.hexsha),
                   commit, [])
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   commit, [])

        # Now add a second version with tag
        assert len(list(model.repo.commits)) == 1
        commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('my_tag', commit2.hexsha)

        # Commits are yielded newest first
        assert len(list(model.repo.commits)) == 2
        assert commit == list(model.repo.commits)[-1]
        commit = model.repo.latest_commit

        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, commit.hexsha),
                   commit, ['my_tag'])
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, 'my_tag'),
                   commit, ['my_tag'])
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   commit, ['my_tag'])

    def test_version_with_two_tags(self, client, helpers):
        model = recipes.model.make()
        helpers.add_version(model, visibility='public')
        commit = model.repo.latest_commit
        model.add_tag('tag1', commit.hexsha)
        model.add_tag('tag2', commit.hexsha)
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, commit.hexsha),
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
        model.set_version_visibility(commit.hexsha, 'public')

        response = client.get(
            '/entities/models/%d/versions/%s' % (model.pk, commit.hexsha),
        )

        assert response.status_code == 200
        assert response.context['visibility'] == 'public'
        assert response.context['form'].initial.get('visibility') == 'public'

    def test_cannot_access_invisible_version(self, client, logged_in_user, helpers):
        model = recipes.model.make()
        commit1 = helpers.add_version(model, visibility='private')
        commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('tag1', commit1.hexsha)

        response = client.get('/entities/models/%d/versions/%s' % (model.pk, commit1.hexsha))
        assert response.status_code == 404

        response = client.get('/entities/models/%d/versions/%s' % (model.pk, 'tag1'))
        assert response.status_code == 404

    def test_anonymous_cannot_access_invisible_version(self, client, helpers):
        model = recipes.model.make()
        commit1 = helpers.add_version(model, visibility='private')
        commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('tag1', commit1.hexsha)

        response = client.get('/entities/models/%d/versions/%s' % (model.pk, commit1.hexsha))
        assert response.status_code == 302

        response = client.get('/entities/models/%d/versions/%s' % (model.pk, 'tag1'))
        assert response.status_code == 302

    def test_no_token_access(self, client, queued_experiment):
        model = queued_experiment.experiment.model
        sha = model.repo.latest_commit.hexsha
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
            '/entities/models/%d/versions/%s' % (model.pk, commit.hexsha)
        )
        assert response.status_code == 404

    def test_404_for_version_not_in_repo(self, client, helpers):
        model = recipes.model.make()
        recipes.cached_entity_version.make(
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
        assert model.get_version_visibility(commit.hexsha) == 'private'

        response = client.post(
            '/entities/models/%d/versions/%s/visibility' % (model.pk, commit.hexsha),
            data={
                'visibility': 'public',
            })

        assert response.status_code == 200
        assert model.get_version_visibility(commit.hexsha) == 'public'
        assert model.repocache.get_version(commit.hexsha).visibility == 'public'

    def test_non_owner_cannot_change_visibility(self, client, logged_in_user, other_user, helpers):
        helpers.login(client, logged_in_user)
        model = recipes.model.make(author=other_user)
        commit = helpers.add_version(model)

        response = client.post(
            '/entities/models/%d/versions/%s/visibility' % (model.pk, commit.hexsha),
            data={
                'visibility': 'public',
            })

        assert response.status_code == 403
        assert model.get_version_visibility(commit.hexsha) != 'public'


@pytest.mark.django_db
class TestEntityVersionJsonView:
    def test_version_json(self, client, logged_in_user, helpers):
        model = recipes.model.make(name='mymodel', author__full_name='model author')
        version = helpers.add_version(model)
        model.set_version_visibility(version.hexsha, 'public')
        model.repo.tag('v1')

        response = client.get('/entities/models/%d/versions/latest/files.json' % model.pk)

        assert response.status_code == 200

        data = json.loads(response.content.decode())
        ver = data['version']

        assert ver['name'] == 'mymodel'
        assert ver['id'] == version.hexsha
        assert ver['author'] == 'model author'
        assert ver['entityId'] == model.pk
        assert ver['visibility'] == 'public'
        assert (
            parse_datetime(ver['created']).replace(microsecond=0) ==
            version.committed_at
        )
        assert ver['version'] == 'v1'
        assert len(ver['files']) == ver['numFiles'] == 1
        assert ver['url'] == '/entities/models/%d/versions/%s' % (model.pk, version.hexsha)
        assert (ver['download_url'] ==
                '/entities/models/%d/versions/%s/archive' % (model.pk, version.hexsha))

    def test_file_json(self, client, helpers):
        model = recipes.model.make()
        version = helpers.add_version(model, visibility='public')
        model.repo.tag('v1')

        response = client.get('/entities/models/%d/versions/latest/files.json' % model.pk)

        assert response.status_code == 200

        data = json.loads(response.content.decode())
        file_ = data['version']['files'][0]
        assert file_['id'] == file_['name'] == 'file1.txt'
        assert file_['filetype'] == 'TXTPROTOCOL'
        assert file_['size'] == 15
        assert (file_['url'] ==
                '/entities/models/%d/versions/%s/download/file1.txt' % (model.pk, version.hexsha))


@pytest.mark.django_db
class TestModelEntityVersionCompareView:
    def test_shows_related_experiments(self, client, experiment_version):
        exp = experiment_version.experiment
        sha = exp.model.repo.latest_commit.hexsha
        recipes.experiment_version.make()  # another experiment which should not be included
        exp.model.set_version_visibility('latest', 'public')
        exp.protocol.set_version_visibility('latest', 'public')

        response = client.get(
            '/entities/models/%d/versions/%s/compare' % (exp.model.pk, sha)
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [(exp.protocol, [exp])]

    def test_applies_visibility(self, client, helpers, experiment_version):
        exp = experiment_version.experiment
        sha = exp.model_version
        protocol = recipes.protocol.make()
        exp.model.set_version_visibility('latest', 'public')
        exp.protocol.set_version_visibility('latest', 'public')

        recipes.experiment_version.make(
            experiment__protocol=protocol,
            experiment__protocol_version=helpers.add_version(protocol, visibility='private').hexsha,
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
class TestProtocolEntityVersionCompareView:
    def test_shows_related_experiments(self, client, logged_in_user, experiment_version):
        exp = experiment_version.experiment
        exp.protocol.set_version_visibility('latest', 'public')
        exp.author = logged_in_user
        exp.save()

        sha = exp.protocol.repo.latest_commit.hexsha
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
            experiment__model_version=helpers.add_version(model, visibility='private').hexsha,
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
    def test_loads_entity_versions(self, client, logged_in_user, model_with_version):
        commit = model_with_version.repo.latest_commit
        version_spec = '%d:%s' % (model_with_version.pk, commit.hexsha)
        response = client.get(
            '/entities/models/compare/%s' % version_spec
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == [version_spec]

    def test_ignores_invalid_versions(self, client, logged_in_user, model_with_version):
        commit = model_with_version.repo.latest_commit
        version_spec = '%d:%s' % (model_with_version.pk, commit.hexsha)
        response = client.get(
            '/entities/models/compare/%s/%d:nocommit' % (version_spec, model_with_version.pk)
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == [version_spec]

    def test_no_valid_versions(self, client, logged_in_user):
        model = recipes.model.make()
        response = client.get(
            '/entities/models/compare/%d:nocommit/%d:nocommit' % (model.pk+1, model.pk)
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == []


@pytest.mark.django_db
class TestEntityComparisonJsonView:
    def test_compare_entities(self, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')
        v2 = helpers.add_version(model)

        v1_spec = '%d:%s' % (model.pk, v1.hexsha)
        v2_spec = '%d:%s' % (model.pk, v2.hexsha)
        response = client.get(
            '/entities/models/compare/%s/%s/info' % (v1_spec, v2_spec)
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        versions = data['getEntityInfos']['entities']
        assert versions[0]['id'] == v1.hexsha
        assert versions[1]['id'] == v2.hexsha
        assert versions[0]['author'] == model.author.full_name
        assert versions[0]['visibility'] == 'public'
        assert versions[0]['name'] == model.name
        assert versions[0]['version'] == v1.hexsha
        assert versions[0]['numFiles'] == 1
        assert versions[0]['commitMessage'] == v1.message

    def test_file_json(self, client, helpers):
        model = recipes.model.make()
        v1 = helpers.add_version(model, visibility='public')

        v1_spec = '%d:%s' % (model.pk, v1.hexsha)
        response = client.get(
            '/entities/models/compare/%s/info' % v1_spec
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        versions = data['getEntityInfos']['entities']
        assert versions[0]['id'] == v1.hexsha
        assert versions[0]['numFiles'] == 1
        file_ = versions[0]['files'][0]
        assert file_['id'] == 'file1.txt'
        assert file_['name'] == 'file1.txt'
        assert file_['author'] == model.author.full_name
        assert file_['filetype'] == 'TXTPROTOCOL'
        #assert file_['masterFile']
        assert file_['size'] == 15
        assert file_['url'] == (
            '/entities/models/%d/versions/%s/download/file1.txt' % (model.pk, v1.hexsha))

    def test_ignores_invalid_versions(self, client, logged_in_user, model_with_version):
        commit = model_with_version.repo.latest_commit
        version_spec = '%d:%s' % (model_with_version.pk, commit.hexsha)
        response = client.get(
            '/entities/models/compare/%s/%d:nocommit' % (version_spec, model_with_version.pk)
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == [version_spec]

    def test_no_valid_versions(self, client, logged_in_user):
        model = recipes.model.make()
        response = client.get(
            '/entities/models/compare/%d:nocommit/%d:nocommit' % (model.pk+1, model.pk)
        )

        assert response.status_code == 200
        assert response.context['entity_versions'] == []


@pytest.mark.django_db
class TestTagging:
    def test_tag_specific_ref(self, helpers):
        model = recipes.model.make()
        commit = helpers.add_version(model)
        helpers.add_version(model)
        model.repo.tag('tag', ref=commit.hexsha)
        tags = model.repo.tag_dict
        assert len(tags) == 1
        assert tags[commit.hexsha][0].name == 'tag'

    def test_nasty_tag_chars(self, helpers):
        import git
        model = recipes.model.make()
        helpers.add_version(model)

        with pytest.raises(git.exc.GitCommandError):
            model.repo.tag('tag/')

        model.repo.tag('my/tag')
        assert model.repo.tag_dict[model.repo.latest_commit.hexsha][0].name == 'my/tag'

        with pytest.raises(git.exc.GitCommandError):
            model.repo.tag('tag with spaces')

    def test_cant_use_same_tag_twice(self, helpers):
        import git
        model = recipes.model.make()
        helpers.add_version(model)
        model.repo.tag('tag')
        helpers.add_version(model)
        with pytest.raises(git.exc.GitCommandError):
            model.repo.tag('tag')

    def test_user_can_add_tag(self, logged_in_user, client, helpers):
        model = recipes.model.make(author=logged_in_user)
        helpers.add_permission(logged_in_user, 'create_model')
        helpers.add_version(model)
        commit = model.repo.latest_commit

        response = client.post(
            '/entities/tag/%d/%s' % (model.pk, commit.hexsha),
            data={
                'tag': 'v1',
            },
        )
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/%s' % (model.pk, commit.hexsha)
        assert 'v1' in model.repo._repo.tags
        tags = model.repo.tag_dict
        assert len(tags) == 1
        assert tags[commit.hexsha][0].name == 'v1'

    def test_cannot_tag_as_non_owner(self, logged_in_user, client, helpers):
        protocol = recipes.protocol.make()
        commit = helpers.add_version(protocol)
        response = client.post(
            '/entities/tag/%d/%s' % (protocol.pk, commit.hexsha),
            data={},
        )
        assert response.status_code == 302

    def test_can_tag_as_non_owner_with_permissions(self, logged_in_user, client, helpers):
        protocol = recipes.protocol.make()
        commit = helpers.add_version(protocol)
        helpers.add_permission(logged_in_user, 'create_protocol')
        assign_perm('edit_entity', logged_in_user, protocol)
        response = client.post(
            '/entities/tag/%d/%s' % (protocol.pk, commit.hexsha),
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
        commit2 = helpers.add_version(model, visibility='public')
        model.add_tag('v1', commit2.hexsha)

        response = client.get('/entities/models/%d/versions/' % model.pk)
        assert response.status_code == 200
        assert response.context['versions'] == [
            (['v1'], commit2),
            ([], commit1),
        ]

    def test_only_shows_visible_versions(self, client, helpers):
        model = recipes.model.make()
        commit1 = helpers.add_version(model, visibility='private')
        commit2 = helpers.add_version(model, visibility='public')

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
        assert 'latest_version' not in response.context
        assert b'option value="private" selected' in response.content

    def test_add_multiple_files(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        model = recipes.model.make(author=logged_in_user)
        recipes.model_file.make(
            entity=model,
            upload=SimpleUploadedFile('file1.txt', b'file 1'),
            original_name='file1.txt',
        )
        recipes.model_file.make(
            entity=model,
            upload=SimpleUploadedFile('file2.txt', b'file 2'),
            original_name='file2.txt',
        )

        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'filename[]': ['uploads/file1.txt', 'uploads/file2.txt'],
                'mainEntry': ['file1.txt'],
                'commit_message': 'files',
                'tag': 'v1',
                'visibility': 'public',
            },
        )
        assert response.status_code == 302
        assert response.url == '/entities/models/%d' % model.id
        assert 'v1' in model.repo._repo.tags

        latest = model.repo.latest_commit
        assert latest.message == 'files'
        assert 'file1.txt' in latest.filenames
        assert 'file2.txt' in latest.filenames
        assert latest.master_filename == 'file1.txt'

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
        assert response.url == '/entities/models/%d' % model.id
        assert 'delete-file' in model.repo._repo.tags

        latest = model.repo.latest_commit
        assert latest.message == 'delete file1'
        assert len(list(latest.files)) == 2
        assert 'file2.txt' in latest.filenames
        assert not (model.repo_abs_path / 'file1.txt').exists()

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
        assert response.url == '/entities/models/%d' % model.id
        assert 'delete-files' in model.repo._repo.tags

        latest = model.repo.latest_commit
        assert latest.message == 'delete files'
        assert len(list(latest.files)) == 2
        assert 'file3.txt' in latest.filenames
        assert not (model.repo_abs_path / 'file1.txt').exists()
        assert not (model.repo_abs_path / 'file2.txt').exists()

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
        assert response.url == '/entities/models/%d' % model.id

    def test_cannot_create_model_version_as_non_owner(self, logged_in_user, client):
        model = recipes.model.make()
        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_create_protocol_version(self, client, logged_in_user, helpers):
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
        assert response.url == '/entities/protocols/%d' % protocol.id
        # Check documentation parsing
        commit = protocol.repo.latest_commit
        assert ProtocolEntity.README_NAME in commit.filenames
        readme = commit.get_blob(ProtocolEntity.README_NAME)
        assert readme.data_stream.read() == doc

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


@pytest.mark.django_db
class TestEntityFileDownloadView:
    def test_download_file(self, client, public_model):
        version = public_model.repo.latest_commit

        response = client.get(
            '/entities/models/%d/versions/%s/download/file1.txt' %
            (public_model.pk, version.hexsha)
        )

        assert response.status_code == 200
        assert response.content == b'entity contents'
        assert response['Content-Disposition'] == (
            'attachment; filename=file1.txt'
        )
        assert response['Content-Type'] == 'text/plain'

    @patch('mimetypes.guess_type', return_value=(None, None))
    def test_uses_octet_stream_for_unknown_file_type(self, mock_guess, client, public_model):
        version = public_model.repo.latest_commit

        response = client.get(
            '/entities/models/%d/versions/%s/download/file1.txt' %
            (public_model.pk, version.hexsha)
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/octet-stream'

    def test_returns_404_for_nonexistent_file(self, client, public_model):
        version = public_model.repo.latest_commit
        response = client.get(
            '/entities/models/%d/versions/%s/download/nonexistent.txt' %
            (public_model.pk, version.hexsha)
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
            'attachment; filename=%s_%s.zip' % (model.name, commit.hexsha)
        )

    def test_returns_404_if_no_commits_yet(self, logged_in_user, client):
        model = recipes.model.make()

        response = client.get('/entities/models/%d/versions/latest/archive' % model.pk)
        assert response.status_code == 404

    def test_anonymous_model_download_for_running_experiment(self, client, queued_experiment):
        model = queued_experiment.experiment.model
        sha = model.repo.latest_commit.hexsha
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
        queued_experiment.experiment.protocol.set_version_visibility('latest', 'private')

        response = client.get(
            '/entities/protocols/%d/versions/latest/archive' % protocol.pk,
            HTTP_AUTHORIZATION='Token {}'.format(queued_experiment.signature)
        )

        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert archive.filelist[0].filename == 'file1.txt'

    def test_public_entity_still_visible_with_invalid_token(self, client, queued_experiment):
        model = queued_experiment.experiment.model
        queued_experiment.experiment.model.set_version_visibility('latest', 'public')

        import uuid
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
        v1 = helpers.add_version(model, contents='v1 contents\n')
        v2 = helpers.add_version(model, contents='v2 contents\n')

        v1_spec = '%d:%s' % (model.pk, v1.hexsha)
        v2_spec = '%d:%s' % (model.pk, v2.hexsha)
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
