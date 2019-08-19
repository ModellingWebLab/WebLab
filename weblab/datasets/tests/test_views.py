import io
import json
import shutil
from pathlib import Path
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
from datasets.models import Dataset


@pytest.mark.django_db
class TestDatasetCreation:
    def test_create_dataset(self, logged_in_user, client, helpers, public_protocol):
        helpers.add_permission(logged_in_user, 'create_dataset', Dataset)
        response = client.post('/datasets/new', data={
            'name': 'mydataset',
            'visibility': 'public',
            'protocol': public_protocol.pk,
            'description': 'description'
        })

        assert response.status_code == 302

        assert Dataset.objects.count() == 1

        dataset = Dataset.objects.first()
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

    def test_create_dataset_with_file(self, client, my_dataset_with_file):
        file_name = 'mydataset.csv'
        file_contents = b'my test dataset'
        # The uploaded file is tidied up
        assert my_dataset_with_file.file_uploads.count() == 0
        # And appears in the archive created
        assert my_dataset_with_file.archive_path.exists()
        assert len(my_dataset_with_file.files) == 1
        assert my_dataset_with_file.files[0].name == file_name
        with my_dataset_with_file.open_file(file_name) as f:
            assert file_contents == f.read()


@pytest.mark.django_db
class TestDatasetView:
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


@pytest.mark.django_db
class TestDatasetsList:
    def test_lists_my_datasets(self, client, logged_in_user):
        datasets = recipes.dataset.make(_quantity=2, author=logged_in_user)
        response = client.get('/datasets/mine')
        assert response.status_code == 200
        assert list(response.context['object_list']) == datasets


@pytest.mark.django_db
class TestDatasetFileDownloadView:
    def test_download_file(self, client, my_dataset_with_file):
        file_contents = b'my test dataset'
        response = client.get(
            '/datasets/%d/download/mydataset.csv' % my_dataset_with_file.pk
        )

        assert response.status_code == 200
        assert response.content == file_contents
        assert response['Content-Disposition'] == (
            'attachment; filename=mydataset.csv'
        )
        assert response['Content-Type'] == 'text/csv'


#     @pytest.mark.parametrize("filename", [
#         ('oxmeta:membrane-voltage with spaces.csv'),
#         ('oxmeta%3Amembrane_voltage.csv'),
#     ])
#     def test_handles_odd_characters(self, logged_in_user, helpers, client, public_protocol, filename):
#         dataset_name = filename[0:len(filename)-4]
#         helpers.add_permission(logged_in_user, 'create_dataset', Dataset)
#         dataset = recipes.dataset.make(author=logged_in_user, name=dataset_name, protocol=public_protocol)
#         file_contents = b'my test dataset'
#         recipes.dataset_file.make(
#             dataset=dataset,
#             upload=SimpleUploadedFile(filename, file_contents),
#             original_name=filename,
#         )
#         client.post(
#             '/datasets/%d/addfiles' % dataset.pk,
#             data={
#                 'filename[]': ['uploads/' + filename],
#                 'delete_filename[]': [],
#                 'mainEntry': [filename],
#             },
#         )
#
#         # neither of these get methods work
#
#
#         # response = client.get(
#         #     '/datasets/%d/download/%s' % (dataset.pk, filename)
#         # )
#
#         # this gives exception No reverse match
#         response = client.get(
#             reverse('datasets:file_download', args=['dataset', dataset.pk, filename])
#         )
#
#         assert response.status_code == 200
# #        assert response.status_code == 404
#         # assert response.content == b'my test dataset'
#         # assert response['Content-Disposition'] == (
#         #     'attachment; filename=' + filename
#         # )
#         # assert response['Content-Type'] == 'text/csv'

    # @pytest.mark.parametrize("filename", [
    #     ('/etc/passwd'),
    #     ('../../../../../pytest.ini'),
    # ])
    # def test_disallows_non_local_files(self, client, my_dataset_with_file, filename):
    #     response = client.get(
    #         '/datasets/%d/download/%s' %
    #         (my_dataset_with_file.pk, filename)
    #     )
    #
    #     assert response.status_code == 404
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
@pytest.mark.django_db
class TestEntityArchiveView:
    def test_download_archive(self, my_dataset_with_file, client):
        response = client.get('/datasets/%d/archive' % my_dataset_with_file.pk)
        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert archive.filelist[0].filename == 'mydataset.csv'
        assert response['Content-Disposition'] == (
            'attachment; filename=%s.zip' % (my_dataset_with_file.name)
        )

    def test_returns_404_if_no_commits_yet(self, my_dataset, client):
        response = client.get('/datasets/%d/archive' % my_dataset.pk)
        assert response.status_code == 404


@pytest.mark.django_db
class TestFileUpload:
    def test_upload_file(self, logged_in_user, client):
        dataset = recipes.dataset.make(author=logged_in_user)

        upload = io.StringIO('my test dataset')
        upload.name = 'dataset.zip'
        response = client.post(
            '/datasets/%d/upload-file' % dataset.pk,
            {
                'upload': upload
            }
        )

        data = json.loads(response.content.decode())
        upload = data['files'][0]
        assert upload['stored_name'] == 'uploads/dataset.zip'
        assert upload['name'] == 'dataset.zip'
        assert upload['is_valid']
        assert upload['size'] == 15

        assert dataset.file_uploads.count() == 1

    def test_bad_upload(self, logged_in_user, client):
        dataset = recipes.dataset.make(author=logged_in_user)

        response = client.post('/datasets/%d/upload-file' % dataset.pk, {})

        assert response.status_code == 400

@pytest.fixture
def archive_file_path():
    return str(Path(__file__).absolute().parent.joinpath('./data1.zip'))


@pytest.mark.django_db
class TestDatasetJsonView:
    def test_dataset_json(self, client, logged_in_user, helpers):
        dataset = recipes.dataset.make(author=logged_in_user)

        response = client.get('/datasets/%d/files.json' % dataset.pk)

        assert response.status_code == 200

        data = json.loads(response.content.decode())
        ver = data['version']

        assert ver['id'] == dataset.id
        assert ver['author'] == 'Test User'
        assert ver['visibility'] == dataset.visibility
        assert ver['name'] == dataset.name
        assert (
            parse_datetime(ver['created']).replace(microsecond=0) ==
            dataset.created_at.replace(microsecond=0)
        )
        assert ver['files'] == []
        assert ver['numFiles'] == 0
        assert (ver['download_url'] ==
                '/datasets/%d/archive' % (dataset.pk))

    # def test_dataset_file_json(self, client, logged_in_user, helpers):
    #     dataset = recipes.dataset.make(author=logged_in_user)
    #     if not dataset.abs_path:
    #         dataset.abs_path.mkdir()
    #     shutil.copyfile(archive_file_path, str(dataset.archive_path))
    #
    #     response = client.get('/datasets/%d/files.json' % dataset.pk)
    #
    #     assert response.status_code == 200
    #
    #     data = json.loads(response.content.decode())
    #     ver = data['version']
    #
    #     file_ = ver['files'][0]
    #     # assert file_['id'] == file_['name'] == 'file1.txt'
    #     # assert file_['filetype'] == 'TXTPROTOCOL'
    #     # assert file_['size'] == 15
    #     # assert (file_['url'] ==
    #     #         '/entities/models/%d/versions/%s/download/file1.txt' % (model.pk, version.hexsha))
    #     #
    #     # if can_create_expt:
    #     #     assert len(ver['planned_experiments']) == 1
    #     #     planned = ver['planned_experiments'][0]
    #     #     assert planned['model'] == model.pk
    #     #     assert planned['model_version'] == version.hexsha
    #     #     assert planned['protocol'] == planned_expt.protocol.pk
    #     #     assert planned['protocol_version'] == str(planned_expt.protocol_version)
    #     # else:
    #     #     assert len(ver['planned_experiments']) == 0
    #     #


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

