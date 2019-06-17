import io
import json
import uuid
import zipfile
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
from datasets.models import ExperimentalDataset


@pytest.mark.django_db
class TestDatasetCreation:
    def test_create_model(self, logged_in_user, client, helpers, public_protocol):
        helpers.add_permission(logged_in_user, 'create_dataset', ExperimentalDataset)
        response = client.post('/datasets/new', data={
            'name': 'mydataset',
            'visibility': 'public',
            'protocol': public_protocol.pk,
            'description': 'description'
        })

        assert response.status_code == 302

        assert ExperimentalDataset.objects.count() == 1

        dataset = ExperimentalDataset.objects.first()
        assert response.url == '/datasets/%d/addfiles' % dataset.id
        assert dataset.name == 'mydataset'
        assert dataset.author == logged_in_user

    def test_create_dataset_requires_permissions(self, logged_in_user, client):
        response = client.post(
            '/datasets/new',
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url


@pytest.mark.django_db
class TestExperimentalDatasetView:
    def test_view_dataset(self, client, logged_in_user, helpers):
        protocol = recipes.protocol.make()
        dataset = recipes.dataset.make(name='mydataset', visibility='public', protocol=protocol)
        response = client.get(
            '/datasets/%d' % dataset.pk)

        assert response.status_code == 200

    def test_shows_correct_visibility(self, client, logged_in_user):
        protocol = recipes.protocol.make()
        dataset = recipes.dataset.make(author=logged_in_user, name='mydataset', visibility='public', protocol=protocol)
        response = client.get(
            '/datasets/%d' % dataset.pk,
        )

        assert response.status_code == 200
        assert response.context_data['object'].visibility == 'public'

        dataset_private = recipes.dataset.make(author=logged_in_user, name='mydataset1', visibility='private', protocol=protocol)
        response = client.get(
            '/datasets/%d' % dataset_private.pk,
        )

        assert response.status_code == 200
        assert response.context_data['object'].visibility == 'private'

    def test_cannot_access_invisible_version(self, client, other_user, logged_in_user):
        protocol = recipes.protocol.make(author=other_user)
        dataset_other = recipes.dataset.make(author=other_user, name='otherdataset', visibility='private', protocol=protocol)
        dataset_mine = recipes.dataset.make(author=logged_in_user, name='mydataset', visibility='private', protocol=protocol)

        # can access mine
        response = client.get(
            '/datasets/%d' % dataset_mine.pk,
        )
        assert response.status_code == 200

        # cannot access someone else's private dataset
        response = client.get(
            '/datasets/%d' % dataset_other.pk,
        )
        assert response.status_code == 404

    def test_shows_correct_protocol(self, client, logged_in_user):
        protocol = recipes.protocol.make(name='myprotocol')
        dataset = recipes.dataset.make(author=logged_in_user, name='mydataset', visibility='public', protocol=protocol)
        response = client.get(
            '/datasets/%d' % dataset.pk,
        )

        assert response.status_code == 200
        assert response.context_data['object'].protocol == protocol


# @pytest.mark.django_db
# class TestEntityList:
#     def test_lists_my_models(self, client, logged_in_user):
#         models = recipes.model.make(_quantity=2, author=logged_in_user)
#         response = client.get('/entities/models/')
#         assert response.status_code == 200
#         assert list(response.context['object_list']) == models
#
#     def test_lists_my_protocols(self, client, logged_in_user):
#         protocols = recipes.protocol.make(_quantity=2, author=logged_in_user)
#         response = client.get('/entities/protocols/')
#         assert response.status_code == 200
#         assert list(response.context['object_list']) == protocols
#
#
# @pytest.mark.django_db
# class TestEntityFileDownloadView:
#     def test_download_file(self, client, public_model):
#         version = public_model.repo.latest_commit
#
#         response = client.get(
#             '/entities/models/%d/versions/%s/download/file1.txt' %
#             (public_model.pk, version.hexsha)
#         )
#
#         assert response.status_code == 200
#         assert response.content == b'entity contents'
#         assert response['Content-Disposition'] == (
#             'attachment; filename=file1.txt'
#         )
#         assert response['Content-Type'] == 'text/plain'
#
#     @pytest.mark.parametrize("filename", [
#         ('oxmeta:membrane-voltage with spaces.csv'),
#         ('oxmeta%3Amembrane_voltage.csv'),
#     ])
#     def test_handles_odd_characters(self, client, helpers, filename):
#         model = recipes.model.make()
#         v1 = helpers.add_version(model, visibility='public', filename=filename)
#
#         response = client.get(
#             reverse('entities:file_download', args=['model', model.pk, v1.hexsha, filename])
#         )
#
#         assert response.status_code == 200
#         assert response.content == b'entity contents'
#         assert response['Content-Disposition'] == (
#             'attachment; filename=' + filename
#         )
#         assert response['Content-Type'] == 'text/csv'
#
#     @pytest.mark.parametrize("filename", [
#         ('/etc/passwd'),
#         ('../../../../../pytest.ini'),
#     ])
#     def test_disallows_non_local_files(self, client, public_model, filename):
#         version = public_model.repo.latest_commit
#
#         response = client.get(
#             '/entities/models/%d/versions/%s/download/%s' %
#             (public_model.pk, version.hexsha, filename)
#         )
#
#         assert response.status_code == 404
#
#     @patch('mimetypes.guess_type', return_value=(None, None))
#     def test_uses_octet_stream_for_unknown_file_type(self, mock_guess, client, public_model):
#         version = public_model.repo.latest_commit
#
#         response = client.get(
#             '/entities/models/%d/versions/%s/download/file1.txt' %
#             (public_model.pk, version.hexsha)
#         )
#
#         assert response.status_code == 200
#         assert response['Content-Type'] == 'application/octet-stream'
#
#     def test_returns_404_for_nonexistent_file(self, client, public_model):
#         version = public_model.repo.latest_commit
#         response = client.get(
#             '/entities/models/%d/versions/%s/download/nonexistent.txt' %
#             (public_model.pk, version.hexsha)
#         )
#
#         assert response.status_code == 404
#
#
# @pytest.mark.django_db
# class TestEntityArchiveView:
#     def test_download_archive(self, client, helpers):
#         model = recipes.model.make()
#         commit = helpers.add_version(model, filename='file1.txt', visibility='public')
#
#         response = client.get('/entities/models/%d/versions/latest/archive' % model.pk)
#         assert response.status_code == 200
#         archive = zipfile.ZipFile(BytesIO(response.content))
#         assert archive.filelist[0].filename == 'file1.txt'
#         assert response['Content-Disposition'] == (
#             'attachment; filename=%s_%s.zip' % (model.name, commit.hexsha)
#         )
#
#     def test_returns_404_if_no_commits_yet(self, logged_in_user, client):
#         model = recipes.model.make()
#
#         response = client.get('/entities/models/%d/versions/latest/archive' % model.pk)
#         assert response.status_code == 404
#
#     def test_anonymous_model_download_for_running_experiment(self, client, queued_experiment):
#         model = queued_experiment.experiment.model
#         sha = model.repo.latest_commit.hexsha
#         queued_experiment.experiment.model.set_version_visibility(sha, 'private')
#
#         response = client.get(
#             '/entities/models/%d/versions/latest/archive' % model.pk,
#             HTTP_AUTHORIZATION='Token {}'.format(queued_experiment.signature)
#         )
#
#         assert response.status_code == 200
#         archive = zipfile.ZipFile(BytesIO(response.content))
#         assert archive.filelist[0].filename == 'file1.txt'
#
#     def test_anonymous_protocol_download_for_running_experiment(self, client, queued_experiment):
#         protocol = queued_experiment.experiment.protocol
#         protocol.set_version_visibility('latest', 'private')
#
#         response = client.get(
#             '/entities/protocols/%d/versions/latest/archive' % protocol.pk,
#             HTTP_AUTHORIZATION='Token {}'.format(queued_experiment.signature)
#         )
#
#         assert response.status_code == 200
#         archive = zipfile.ZipFile(BytesIO(response.content))
#         assert archive.filelist[0].filename == 'file1.txt'
#
#     def test_anonymous_protocol_download_for_analysis_task(self, client, analysis_task):
#         protocol = analysis_task.entity
#         protocol.set_version_visibility('latest', 'private')
#
#         response = client.get(
#             '/entities/protocols/%d/versions/latest/archive' % protocol.pk,
#             HTTP_AUTHORIZATION='Token {}'.format(analysis_task.id)
#         )
#
#         assert response.status_code == 200
#         archive = zipfile.ZipFile(BytesIO(response.content))
#         assert archive.filelist[0].filename == 'file1.txt'
#
#     def test_public_entity_still_visible_with_invalid_token(self, client, queued_experiment):
#         model = queued_experiment.experiment.model
#         queued_experiment.experiment.model.set_version_visibility('latest', 'public')
#
#         response = client.get(
#             '/entities/models/%d/versions/latest/archive' % model.pk,
#             HTTP_AUTHORIZATION='Token {}'.format(uuid.uuid4())
#         )
#
#         assert response.status_code == 200
#         archive = zipfile.ZipFile(BytesIO(response.content))
#         assert archive.filelist[0].filename == 'file1.txt'
#
#
# @pytest.mark.django_db
# class TestFileUpload:
#     def test_upload_file(self, logged_in_user, client):
#         model = recipes.model.make(author=logged_in_user)
#
#         upload = io.StringIO('my test model')
#         upload.name = 'model.txt'
#         response = client.post(
#             '/entities/%d/upload-file' % model.pk,
#             {
#                 'upload': upload
#             }
#         )
#
#         data = json.loads(response.content.decode())
#         upload = data['files'][0]
#         assert upload['stored_name'] == 'uploads/model.txt'
#         assert upload['name'] == 'model.txt'
#         assert upload['is_valid']
#         assert upload['size'] == 13
#
#         assert model.files.count() == 1
#
#     def test_bad_upload(self, logged_in_user, client):
#         model = recipes.model.make(author=logged_in_user)
#
#         response = client.post('/entities/%d/upload-file' % model.pk, {})
#
#         assert response.status_code == 400
#
#
# @pytest.mark.django_db
# @pytest.mark.parametrize("recipe,url", [
#     (recipes.model, '/entities/models/%d'),
#     (recipes.model, '/entities/models/%d/versions/'),
#     (recipes.model, '/entities/models/%d/versions/latest'),
#     (recipes.model, '/entities/models/%d/versions/latest/compare'),
#     (recipes.model, '/entities/models/%d/versions/latest/archive'),
#     (recipes.model, '/entities/models/%d/versions/latest/files.json'),
#     (recipes.model, '/entities/models/%d/versions/latest/download/file1.txt'),
#     (recipes.protocol, '/entities/protocols/%d'),
#     (recipes.protocol, '/entities/protocols/%d/versions/'),
#     (recipes.protocol, '/entities/protocols/%d/versions/latest'),
#     (recipes.protocol, '/entities/protocols/%d/versions/latest/compare'),
#     (recipes.protocol, '/entities/protocols/%d/versions/latest/archive'),
#     (recipes.protocol, '/entities/protocols/%d/versions/latest/files.json'),
#     (recipes.protocol, '/entities/protocols/%d/versions/latest/download/file1.txt'),
# ])
# class TestEntityVisibility:
#     def test_private_entity_visible_to_self(self, client, logged_in_user, helpers, recipe, url):
#         entity = recipe.make(author=logged_in_user)
#         helpers.add_version(entity, visibility='private')
#         assert client.get(url % entity.pk, follow=True).status_code == 200
#
#     def test_private_entity_visible_to_collaborator(self, client, logged_in_user, helpers, recipe, url):
#         entity = recipe.make()
#         helpers.add_version(entity, visibility='private')
#         assign_perm('edit_entity', logged_in_user, entity)
#         assert client.get(url % entity.pk, follow=True).status_code == 200
#
#     def test_private_entity_invisible_to_other_user(
#         self,
#         client, logged_in_user, other_user, helpers,
#         recipe, url
#     ):
#         entity = recipe.make(author=other_user)
#         helpers.add_version(entity, visibility='private')
#         response = client.get(url % entity.pk)
#         assert response.status_code == 404
#
#     def test_private_entity_requires_login_for_anonymous(self, client, helpers, recipe, url):
#         entity = recipe.make()
#         helpers.add_version(entity, visibility='private')
#         response = client.get(url % entity.pk)
#         assert response.status_code == 302
#         assert '/login' in response.url
#
#     def test_public_entity_visible_to_anonymous(self, client, helpers, recipe, url):
#         entity = recipe.make()
#         helpers.add_version(entity, visibility='public')
#         assert client.get(url % entity.pk, follow=True).status_code == 200
#
#     def test_public_entity_visible_to_logged_in_user(self, client, logged_in_user, helpers, recipe, url):
#         entity = recipe.make()
#         helpers.add_version(entity, visibility='public')
#         assert client.get(url % entity.pk, follow=True).status_code == 200
#
#     def test_nonexistent_entity_redirects_anonymous_to_login(self, client, helpers, recipe, url):
#         response = client.get(url % 10000)
#         assert response.status_code == 302
#         assert '/login' in response.url
#
#     def test_nonexistent_entity_generates_404_for_user(self, client, logged_in_user, helpers, recipe, url):
#         response = client.get(url % 10000)
#         assert response.status_code == 404
#

