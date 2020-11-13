import io
import json
import os
import zipfile
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.dateparse import parse_datetime

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

    def test_create_dataset_with_same_name(self, logged_in_user, other_user, client, helpers, public_protocol):
        helpers.add_permission(other_user, 'create_dataset', Dataset)
        helpers.add_permission(logged_in_user, 'create_dataset', Dataset)
        recipes.dataset.make(author=other_user, name='mydataset', protocol=public_protocol)

        response = client.post('/datasets/new', data={
            'name': 'mydataset',
            'visibility': 'public',
            'protocol': public_protocol.pk,
            'description': 'description'
        })

        assert response.status_code == 302
        assert Dataset.objects.count() == 2

    def test_create_dataset_requires_permissions(self, logged_in_user, client):
        response = client.post(
            '/datasets/new',
            data={},
        )
        assert response.status_code == 403

    def test_create_dataset_with_file(self, client, my_dataset_with_file):
        # These match what the fixture sets up
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

    def test_add_delete_add_file(self, logged_in_user, client, helpers, public_protocol):
        helpers.add_permission(logged_in_user, 'create_dataset', Dataset)
        dataset = recipes.dataset.make(author=logged_in_user, name='mydataset', protocol=public_protocol)
        file_name = 'mydataset.csv'
        file_contents = b'my test dataset'
        del1 = recipes.dataset_file.make(  # Uploaded then deleted
            dataset=dataset,
            upload=SimpleUploadedFile(file_name, file_contents),
            original_name=file_name,
        )
        file_name_rep = 'mydatasetr.csv'
        del2 = recipes.dataset_file.make(  # Uploaded then replaced by alternative version
            dataset=dataset,
            upload=SimpleUploadedFile(file_name_rep, b'my test original dataset'),
            original_name=file_name_rep,
        )
        file_name2 = 'mydataset2.csv'
        file_contents2 = b'my test dataset2'
        file_upload2 = recipes.dataset_file.make(  # Uploaded and kept
            dataset=dataset,
            upload=SimpleUploadedFile(file_name2, file_contents2),
            original_name=file_name2,
        )
        file_contents_rep = b'my test dataset2'
        file_upload_rep = recipes.dataset_file.make(  # Replacement version of mydatasetr.csv
            dataset=dataset,
            upload=SimpleUploadedFile(file_name_rep, file_contents_rep),
            original_name=file_name_rep,
        )
        response = client.post(
            '/datasets/%d/addfiles' % dataset.pk,
            data={
                'filename[]': [str(file_upload2.upload), str(file_upload_rep.upload)],
                'delete_filename[]': [file_name, file_name_rep],
                'mainEntry': [file_name],
            },
        )
        assert response.status_code == 302
        assert response.url == '/datasets/%d/map' % dataset.pk
        # Check uploads have been cleared & files removed
        assert dataset.file_uploads.count() == 0
        assert not os.path.exists(del1.upload.path)
        assert not os.path.exists(del2.upload.path)
        assert not os.path.exists(file_upload2.upload.path)
        assert not os.path.exists(file_upload_rep.upload.path)
        # And correct files appear in the archive created
        assert dataset.archive_path.exists()
        assert len(dataset.files) == 2
        file_map = {
            file_name2: file_contents2,
            file_name_rep: file_contents_rep,
        }
        for f in dataset.files:
            assert f.name in file_map
            with dataset.open_file(f.name) as fp:
                assert fp.read() == file_map[f.name]


@pytest.mark.django_db
class TestDatasetRenaming:
    def test_dataset_renaming_success(self, client, my_dataset_with_file):

        dataset = my_dataset_with_file
        old_path = dataset.archive_path
        assert old_path.exists()
        assert dataset.name == 'mydataset'

        response = client.post(
            '/datasets/%d/rename' % dataset.pk,
            data={
                'name': 'new name'
            })
        assert response.status_code == 302

        dataset = Dataset.objects.first()
        assert not old_path.exists()
        assert dataset.archive_path.exists()
        assert dataset.name == 'new name'

    def test_dataset_renaming_different_users_succeeds(self, client, logged_in_user, helpers):
        dataset = recipes.dataset.make(author=logged_in_user)

        dataset2 = recipes.dataset.make(name='test dataset 2')
        assert dataset.name == 'my dataset1'
        assert dataset2.name == 'test dataset 2'

        response = client.post(
            '/datasets/%d/rename' % dataset.pk,
            data={
                'name': 'test dataset 2'
            })
        assert response.status_code == 302
        dataset = Dataset.objects.first()
        assert dataset.name == 'test dataset 2'

    def test_dataset_renaming_same_users_fails(self, client, logged_in_user, helpers):
        dataset = recipes.dataset.make(author=logged_in_user)

        dataset2 = recipes.dataset.make(author=logged_in_user, name='test dataset 2')
        assert dataset.name == 'my dataset1'
        assert dataset2.name == 'test dataset 2'

        response = client.post(
            '/datasets/%d/rename' % dataset.pk,
            data={
                'name': 'test dataset 2'
            })
        assert response.status_code == 200
        dataset = Dataset.objects.first()
        assert dataset.name == 'my dataset1'


@pytest.mark.django_db
class TestDatasetDeletion:

    def test_owner_can_delete_dataset_with_file(
            self, logged_in_user, client, my_dataset_with_file
    ):
        dataset = my_dataset_with_file
        assert Dataset.objects.filter(pk=dataset.pk).exists()
        assert dataset.archive_path.exists()
        response = client.post('/datasets/%d/delete' % dataset.pk)
        assert response.status_code == 302
        assert response.url == '/datasets/'
        assert not Dataset.objects.filter(pk=dataset.pk).exists()
        assert not dataset.archive_path.exists()

    def test_owner_can_delete_dataset_without_file(
            self, logged_in_user, client, my_dataset
    ):
        dataset = my_dataset
        assert Dataset.objects.filter(pk=dataset.pk).exists()
        response = client.post('/datasets/%d/delete' % dataset.pk)
        assert response.status_code == 302
        assert response.url == '/datasets/'
        assert not Dataset.objects.filter(pk=dataset.pk).exists()

    def test_non_owner_cannot_delete_dataset(
            self, helpers, other_user, logged_in_user, public_protocol, client
    ):
        helpers.add_permission(other_user, 'create_dataset', Dataset)
        dataset = recipes.dataset.make(author=other_user, name='mydataset', protocol=public_protocol)
        file_name = 'mydataset.csv'
        file_contents = b'my test dataset'
        recipes.dataset_file.make(
            dataset=dataset,
            upload=SimpleUploadedFile(file_name, file_contents),
            original_name=file_name,
        )
        client.post(
            '/datasets/%d/addfiles' % dataset.pk,
            data={
                'filename[]': ['uploads/' + file_name],
                'delete_filename[]': [],
                'mainEntry': [file_name],
            },
        )
        assert Dataset.objects.filter(pk=dataset.pk).exists()
        assert dataset.archive_path.exists()
        response = client.post('/datasets/%d/delete' % dataset.pk)
        assert response.status_code == 403
        assert Dataset.objects.filter(pk=dataset.pk).exists()
        assert dataset.archive_path.exists()

    def test_admin_can_delete_dataset(
            self, helpers, other_user, logged_in_admin, public_protocol, client
    ):
        helpers.add_permission(other_user, 'create_dataset', Dataset)
        dataset = recipes.dataset.make(author=other_user, name='mydataset', protocol=public_protocol)
        file_name = 'mydataset.csv'
        file_contents = b'my test dataset'
        recipes.dataset_file.make(
            dataset=dataset,
            upload=SimpleUploadedFile(file_name, file_contents),
            original_name=file_name,
        )
        client.post(
            '/datasets/%d/addfiles' % dataset.pk,
            data={
                'filename[]': ['uploads/' + file_name],
                'delete_filename[]': [],
                'mainEntry': [file_name],
            },
        )
        assert Dataset.objects.filter(pk=dataset.pk).exists()
        assert dataset.archive_path.exists()
        response = client.post('/datasets/%d/delete' % dataset.pk)
        assert response.status_code == 302
        assert response.url == '/datasets/'
        assert not Dataset.objects.filter(pk=dataset.pk).exists()
        assert not dataset.archive_path.exists()


@pytest.mark.django_db
class TestTransferDatasetView:

    def test_datasets_transfer_success(self, client, logged_in_user, other_user, my_dataset_with_file, helpers):
        dataset = my_dataset_with_file
        oldpath = dataset.archive_path
        assert oldpath.exists()
        assert dataset.author.email == 'test@example.com'
        response = client.post(
            '/datasets/%d/transfer' % dataset.pk,
            data={
                'email': other_user.email,
            },
        )
        assert response.status_code == 302
        dataset.refresh_from_db()
        assert dataset.author == other_user
        assert not oldpath.exists()
        assert not oldpath.parent.exists()
        assert dataset.archive_path.exists()

    def test_datasets_transfer_success_no_file(self, client, logged_in_user, other_user, my_dataset, helpers):
        dataset = my_dataset
        assert dataset.author.email == 'test@example.com'
        response = client.post(
            '/datasets/%d/transfer' % dataset.pk,
            data={
                'email': other_user.email,
            },
        )
        assert response.status_code == 302
        dataset.refresh_from_db()
        assert dataset.author == other_user

    def test_datasets_transfer_fail_invalid_user(self, client, logged_in_user, other_user, my_dataset, helpers):
        dataset = my_dataset
        assert dataset.author.email == 'test@example.com'
        response = client.post(
            '/datasets/%d/transfer' % dataset.pk,
            data={
                'email': 'invalid@example.com',
            },
        )
        assert response.status_code == 200
        dataset.refresh_from_db()
        assert dataset.author == logged_in_user

    def test_datasets_transfer_fail_same_name(self, client, logged_in_user, other_user, my_dataset, helpers):
        protocol = recipes.protocol.make()
        recipes.dataset.make(author=other_user, name='mydataset', visibility='public', protocol=protocol)
        dataset = my_dataset
        assert dataset.author.email == 'test@example.com'
        response = client.post(
            '/datasets/%d/transfer' % dataset.pk,
            data={
                'email': other_user.email,
            },
        )
        assert response.status_code == 200
        dataset.refresh_from_db()
        assert dataset.author == logged_in_user


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

        dataset_private = recipes.dataset.make(
            author=logged_in_user, name='mydataset1', visibility='private', protocol=protocol)
        response = client.get(
            '/datasets/%d' % dataset_private.pk,
        )

        assert response.status_code == 200
        assert response.context_data['object'].visibility == 'private'

    def test_cannot_access_invisible_version(self, client, other_user, logged_in_user):
        protocol = recipes.protocol.make(author=other_user)
        dataset_other = recipes.dataset.make(
            author=other_user, name='otherdataset', visibility='private', protocol=protocol)
        dataset_mine = recipes.dataset.make(
            author=logged_in_user, name='mydataset', visibility='private', protocol=protocol)

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
    def test_lists_my_datasets(self, client, logged_in_user, other_user):
        datasets = recipes.dataset.make(_quantity=2, author=logged_in_user)
        recipes.dataset.make(_quantity=1, author=other_user)
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

    @pytest.mark.parametrize("filename", [
        ('oxmeta:membrane-voltage with spaces.csv'),
        # ('oxmeta%3Amembrane_voltage.csv'),  # You can't upload a file with this name
    ])
    def test_handles_odd_characters(self, logged_in_user, helpers, client, public_protocol, filename):
        helpers.add_permission(logged_in_user, 'create_dataset', Dataset)
        dataset = recipes.dataset.make(author=logged_in_user, name="dataset", protocol=public_protocol)
        file_contents = b'my test dataset'
        file_upload = recipes.dataset_file.make(
            dataset=dataset,
            upload=SimpleUploadedFile(filename, file_contents),
            original_name=filename,
        )
        response = client.post(
            '/datasets/%d/addfiles' % dataset.pk,
            data={
                'filename[]': [str(file_upload.upload)],
                'delete_filename[]': [],
                'mainEntry': [file_upload.original_name],
            },
        )
        # Check file added OK
        assert response.status_code == 302
        assert response.url == '/datasets/%d/map' % dataset.pk

        response = client.get(
            reverse('datasets:file_download', args=[dataset.pk, filename])
        )

        assert response.status_code == 200
        assert response.content == b'my test dataset'
        assert response['Content-Disposition'] == (
            'attachment; filename=' + filename
        )
        assert response['Content-Type'] == 'text/csv'

    @pytest.mark.parametrize("filename", [
        ('/etc/passwd'),
        ('../../../../../pytest.ini'),
    ])
    def test_disallows_non_local_files(self, client, my_dataset_with_file, filename):
        response = client.get(
            '/datasets/%d/download/%s' %
            (my_dataset_with_file.pk, filename)
        )

        assert response.status_code == 404

    @patch('mimetypes.guess_type', return_value=(None, None))
    def test_uses_octet_stream_for_unknown_file_type(self, mock_guess, my_dataset_with_file, client):
        response = client.get(
            '/datasets/%d/download/%s' %
            (my_dataset_with_file.pk, 'mydataset.csv')
        )

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/octet-stream'

    def test_returns_404_for_nonexistent_file(self, my_dataset_with_file, client):
        response = client.get(
            '/datasets/%d/download/non_existent.csv' % my_dataset_with_file.pk
        )

        assert response.status_code == 404


@pytest.mark.django_db
class TestDatasetArchiveView:
    def test_anonymous_dataset_download_for_running_fittingresult(
        self, client, queued_fittingresult, my_dataset_with_file,
    ):
        queued_fittingresult.fittingresult.dataset = my_dataset_with_file
        queued_fittingresult.fittingresult.save()

        response = client.get(
            '/datasets/%d/archive' % my_dataset_with_file.pk,
            HTTP_AUTHORIZATION='Token {}'.format(queued_fittingresult.signature)
        )

        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert archive.filelist[0].filename == 'mydataset.csv'

    def test_download_archive(self, my_dataset_with_file, client):
        response = client.get('/datasets/%d/archive' % my_dataset_with_file.pk)
        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert archive.filelist[0].filename == 'mydataset.csv'
        assert response['Content-Disposition'] == (
            'attachment; filename=%s.zip' % (my_dataset_with_file.name)
        )

    def test_returns_404_if_no_files_yet(self, my_dataset, client):
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


@pytest.mark.django_db
class TestDatasetJsonView:
    def test_dataset_json(self, client, logged_in_user, helpers):
        dataset = recipes.dataset.make(author=logged_in_user)

        response = client.get('/datasets/%d/files.json' % dataset.pk)

        assert response.status_code == 200

        data = json.loads(response.content.decode())
        ver = data['version']

        assert ver['id'] == dataset.id
        assert ver['author'] == logged_in_user.full_name
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

    def test_dataset_file_json(self, my_dataset_with_file, client):
        dataset = my_dataset_with_file

        response = client.get('/datasets/%d/files.json' % dataset.pk)

        assert response.status_code == 200

        data = json.loads(response.content.decode())
        ver = data['version']

        file_ = ver['files'][0]
        assert file_['id'] == file_['name'] == 'mydataset.csv'
        assert file_['filetype'] == 'http://purl.org/NET/mediatypes/text/csv'
        assert file_['size'] == 15
        assert (file_['url'] ==
                '/datasets/%d/download/mydataset.csv' % dataset.pk)


# note this does not test the archive/download url because of
# how difficult it is to make a dummy dataset with a file
@pytest.mark.django_db
@pytest.mark.parametrize("recipe,url", [
    (recipes.dataset, '/datasets/%d'),
    (recipes.dataset, '/datasets/%d/files.json'),
])
class TestDatasetVisibility:
    def test_private_dataset_visible_to_self(self, client, logged_in_user, helpers, public_protocol, recipe, url):
        dataset = recipe.make(author=logged_in_user, visibility='private', protocol=public_protocol)
        assert client.get(url % dataset.pk, follow=True).status_code == 200

    # this permission does not exist  - should it ?
    # def test_private_dataset_visible_to_collaborator(self, dataset_creator, client, logged_in_user, helpers,
    #                                                 public_protocol, recipe, url):
    #     dataset = recipe.make(author=dataset_creator, visibility='private', protocol=public_protocol)
    #     assign_perm('edit_dataset', logged_in_user, dataset)
    #     assert client.get(url % dataset.pk, follow=True).status_code == 200

    def test_private_dataset_invisible_to_other_user(
        self,
        client, logged_in_user, other_user, helpers, public_protocol,
        recipe, url
    ):
        dataset = recipe.make(author=other_user, visibility='private', protocol=public_protocol)
        response = client.get(url % dataset.pk)
        assert response.status_code == 404

    def test_private_dataset_requires_login_for_anonymous(self, client, helpers,
                                                          dataset_creator, public_protocol,
                                                          recipe, url):
        dataset = recipe.make(author=dataset_creator, visibility='private', protocol=public_protocol)
        response = client.get(url % dataset.pk)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_public_dataset_visible_to_anonymous(self, client, helpers,
                                                 dataset_creator, public_protocol,
                                                 recipe, url):
        dataset = recipe.make(author=dataset_creator, visibility='private', protocol=public_protocol)
        assert client.get(url % dataset.pk, follow=True).status_code == 200

    def test_public_dataset_visible_to_logged_in_user(self, client, logged_in_user, helpers,
                                                      dataset_creator, public_protocol,
                                                      recipe, url):
        dataset = recipe.make(author=dataset_creator, visibility='private', protocol=public_protocol)
        assert client.get(url % dataset.pk, follow=True).status_code == 200

    def test_nonexistent_dataset_redirects_anonymous_to_login(self, client, helpers, recipe, url):
        response = client.get(url % 10000)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_nonexistent_dataset_generates_404_for_user(self, client, logged_in_user, helpers, recipe, url):
        response = client.get(url % 10000)
        assert response.status_code == 404


@pytest.mark.django_db
class TestDatasetCompareFittingResultsView:
    def test_shows_fittings_related_to_dataset(self, client, fittingresult_version):
        fit = fittingresult_version.fittingresult

        # should not be included, as it uses a different dataset
        recipes.fittingresult_version.make()

        response = client.get('/datasets/%d/fittings' % fit.dataset.pk)

        assert response.status_code == 200
        assert response.context['comparisons'] == [(fit.model, [fit])]

    def test_groups_by_model(self, client, helpers, public_dataset):
        m1, m2 = recipes.model.make(_quantity=2)
        m1v = helpers.add_cached_version(m1, visibility='public')
        m2v = helpers.add_cached_version(m2, visibility='public')

        # Create publicly visible fitting result versions
        fit1_m1 = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__model=m1,
            fittingresult__model_version=m1v,
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        fit2_m1 = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__model=m1,
            fittingresult__model_version=m1v,
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        fit3_m2 = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__model=m2,
            fittingresult__model_version=m2v,
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        response = client.get('/datasets/%d/fittings' % public_dataset.id)

        assert response.status_code == 200
        assert response.context['comparisons'] == [
            (m1, [fit2_m1, fit1_m1]),
            (m2, [fit3_m2]),
        ]

    def test_multiple_model_versions_for_dataset(self, client, helpers, public_dataset):
        m1, m2 = recipes.model.make(_quantity=2)
        m1v1 = helpers.add_cached_version(m1, visibility='public')
        m1v2 = helpers.add_cached_version(m1, visibility='public')
        m2v = helpers.add_cached_version(m2, visibility='public')

        # Create publicly visible fitting result versions
        fit1_m1v1 = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__model=m1,
            fittingresult__model_version=m1v1,
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        fit2_m1v2 = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__model=m1,
            fittingresult__model_version=m1v2,
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        fit3_m2v = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__model=m2,
            fittingresult__model_version=m2v,
            fittingresult__fittingspec_version__visibility='public',
            fittingresult__protocol_version__visibility='public',
        ).fittingresult

        response = client.get(
            '/datasets/%d/fittings' % public_dataset.id
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [
            (m1, [fit2_m1v2, fit1_m1v1]),
            (m2, [fit3_m2v]),
        ]

    def test_ensure_private_results_are_not_shown(self, client, public_dataset):
        recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__model_version__visibility='private',
            fittingresult__protocol_version__visibility='public',
            fittingresult__fittingspec_version__visibility='public',
        )

        recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__model_version__visibility='public',
            fittingresult__protocol_version__visibility='private',
            fittingresult__fittingspec_version__visibility='public',
        )

        recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__model_version__visibility='public',
            fittingresult__protocol_version__visibility='public',
            fittingresult__fittingspec_version__visibility='private',
        )

        fit = recipes.fittingresult_version.make(
            fittingresult__dataset=public_dataset,
            fittingresult__model_version__visibility='public',
            fittingresult__protocol_version__visibility='public',
            fittingresult__fittingspec_version__visibility='public',
        ).fittingresult

        response = client.get(
            '/datasets/%d/fittings' % public_dataset.id
        )

        assert response.status_code == 200
        assert response.context['comparisons'] == [
            (fit.model, [fit]),
        ]


@pytest.mark.django_db
class TestDatasetMapColumnsView:
    def test_owner_can_map_dataset(self, logged_in_user, public_protocol, client):
        my_dataset = recipes.dataset.make(
            author=logged_in_user, visibility='public', protocol=public_protocol)
        response = client.get('/datasets/%d/map' % my_dataset.pk)
        assert response.status_code == 200

        response = client.post('/datasets/%d/map' % my_dataset.pk)
        assert response.status_code == 302

    def test_non_owner_cannot_map_dataset(
            self, helpers, other_user, logged_in_user, public_protocol, client
    ):
        other_dataset = recipes.dataset.make(
            author=other_user, visibility='public', protocol=public_protocol)
        response = client.get('/datasets/%d/map' % other_dataset.pk)
        assert response.status_code == 403

        response = client.post('/datasets/%d/map' % other_dataset.pk)
        assert response.status_code == 403

    def test_has_form_for_each_version_and_column(self, client, logged_in_user, helpers, mock_column_names):
        mock_column_names.return_value = ['col1', 'col2']
        protocol = recipes.protocol.make()
        proto_v1 = helpers.add_fake_version(protocol, visibility='public')
        proto_v2 = helpers.add_fake_version(protocol, visibility='public')
        # But not private version
        proto_v3 = helpers.add_fake_version(protocol, visibility='private')

        dataset = recipes.dataset.make(visibility='public', protocol=protocol, author=logged_in_user)

        response = client.get('/datasets/%d/map' % dataset.pk)

        assert response.status_code == 200
        assert response.context['forms']
        forms = response.context['forms']
        assert proto_v1 in forms
        assert proto_v2 in forms
        assert proto_v3 not in forms
        assert len(forms[proto_v1]) == 2
        assert len(forms[proto_v2]) == 2

    def test_restricts_ioputs_to_protocol_version(self, client, logged_in_user, helpers, mock_column_names):
        protocol = recipes.protocol.make()
        proto_v1 = helpers.add_fake_version(protocol, visibility='public')
        proto_v2 = helpers.add_fake_version(protocol, visibility='public')

        v1_in = recipes.protocol_input.make(protocol_version=proto_v1)
        v1_out = recipes.protocol_output.make(protocol_version=proto_v1)
        v1_flag = recipes.protocol_ioput_flag.make(protocol_version=proto_v1)

        v2_in = recipes.protocol_input.make(protocol_version=proto_v2)

        dataset = recipes.dataset.make(visibility='public', protocol=protocol, author=logged_in_user)

        response = client.get('/datasets/%d/map' % dataset.pk)

        assert response.status_code == 200
        assert response.context['forms']
        v1_form = response.context['forms'][proto_v1][0]
        pv_field = v1_form.fields['protocol_ioput']

        assert pv_field.valid_value(v1_in.pk)
        assert pv_field.valid_value(v1_out.pk)
        assert not pv_field.valid_value(v1_flag.pk)
        assert not pv_field.valid_value(v2_in.pk)

    def test_creates_new_column_mapping(self, client, logged_in_user, public_protocol, mock_column_names):
        proto_v1 = public_protocol.repocache.latest_version
        proto_v1_in = recipes.protocol_input.make(protocol_version=proto_v1)

        dataset = recipes.dataset.make(visibility='public', protocol=public_protocol, author=logged_in_user)

        prefix = 'mapping_%d_0-' % proto_v1.pk
        response = client.post(
            '/datasets/%d/map' % dataset.pk,
            {
                prefix + 'dataset': dataset.pk,
                prefix + 'column_name': 'col',
                prefix + 'column_units': 'meters',
                prefix + 'protocol_version': proto_v1.pk,
                prefix + 'protocol_ioput': proto_v1_in.pk,
            },
        )

        assert response.status_code == 302
        assert dataset.column_mappings.count() == 1

    def test_overwrites_existing_column_mapping(self, client, logged_in_user, public_protocol, mock_column_names):
        proto_v1 = public_protocol.repocache.latest_version
        proto_v1_in = recipes.protocol_input.make(protocol_version=proto_v1)

        dataset = recipes.dataset.make(
            visibility='public', protocol=public_protocol, author=logged_in_user)

        mapping = recipes.column_mapping.make(
            dataset=dataset,
            protocol_version=proto_v1,
            protocol_ioput=proto_v1_in,
            column_name='col',
            column_units='meters'
        )

        prefix = 'mapping_%d_0-' % proto_v1.pk
        response = client.post(
            '/datasets/%d/map' % dataset.pk,
            {
                prefix + 'id': mapping.pk,
                prefix + 'dataset': dataset.pk,
                prefix + 'column_name': 'col',
                prefix + 'column_units': 'seconds',
                prefix + 'protocol_version': proto_v1.pk,
                prefix + 'protocol_ioput': proto_v1_in.pk,
            },
        )

        assert response.status_code == 302
        assert dataset.column_mappings.count() == 1
        assert dataset.column_mappings.get(column_name='col').column_units == 'seconds'
