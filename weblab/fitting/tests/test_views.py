import json
import shutil
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from django.core.urlresolvers import reverse
from django.utils.dateparse import parse_datetime
from pytest_django.asserts import assertContains, assertTemplateUsed

from fitting.models import FittingResult, FittingResultVersion


@pytest.fixture
def archive_file_path():
    return str(Path(__file__).absolute().parent.joinpath('./test.omex'))


@pytest.mark.django_db
class TestFittingResultVersionsView:
    def test_view_fittingresult_versions(self, client, fittingresult_version):
        response = client.get(
            ('/fitting/results/%d/versions/' % fittingresult_version.fittingresult.pk)
        )

        assert response.status_code == 200
        assert response.context['fittingresult'] == fittingresult_version.fittingresult


@pytest.mark.django_db
class TestFittingResultVersionView:
    def test_view_fittingresult_version(self, client, fittingresult_version):
        response = client.get(
            ('/fitting/results/%d/versions/%d' %
             (fittingresult_version.fittingresult.pk, fittingresult_version.pk))
        )

        assert response.context['version'] == fittingresult_version
        assertTemplateUsed(response, 'fitting/fittingresultversion_detail.html')
        assertContains(response, 'Download archive of all files')


@pytest.mark.django_db
class TestFittingResultArchiveView:
    def test_download_archive(self, client, fittingresult_version, archive_file_path):
        fittingresult_version.mkdir()
        fittingresult_version.fittingresult.model.name = 'my_model'
        fittingresult_version.fittingresult.model.save()
        fittingresult_version.fittingresult.fittingspec.name = 'my_spec'
        fittingresult_version.fittingresult.fittingspec.save()
        fittingresult_version.fittingresult.dataset.name = 'my_dataset'
        fittingresult_version.fittingresult.dataset.save()
        shutil.copyfile(archive_file_path, str(fittingresult_version.archive_path))

        response = client.get(
            '/fitting/results/%d/versions/%d/archive' %
            (fittingresult_version.fittingresult.pk, fittingresult_version.pk)
        )
        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert set(archive.namelist()) == {
            'stdout.txt', 'errors.txt', 'manifest.xml', 'oxmeta:membrane%3Avoltage - space.csv'}
        assert response['Content-Disposition'] == (
            'attachment; filename=Fit_my_model_to_my_dataset_using_my_spec.zip'
        )

    def test_returns_404_if_no_archive_exists(self, client, fittingresult_version):
        response = client.get(
            '/fitting/results/%d/versions/%d/archive' %
            (fittingresult_version.fittingresult.pk, fittingresult_version.pk)
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestFittingResultFileDownloadView:
    def test_download_file(self, client, archive_file_path, fittingresult_version):
        fittingresult_version.mkdir()
        shutil.copyfile(archive_file_path, str(fittingresult_version.archive_path))

        response = client.get(
            '/fitting/results/%d/versions/%d/download/stdout.txt' %
            (fittingresult_version.fittingresult.pk, fittingresult_version.pk)
        )
        assert response.status_code == 200
        assert response.content == b'line of output\nmore output\n'
        assert response['Content-Disposition'] == (
            'attachment; filename=stdout.txt'
        )
        assert response['Content-Type'] == 'text/plain'

    def test_handles_odd_characters(self, client, archive_file_path, fittingresult_version):
        fittingresult_version.mkdir()
        shutil.copyfile(archive_file_path, str(fittingresult_version.archive_path))
        filename = 'oxmeta:membrane%3Avoltage - space.csv'

        response = client.get(
            reverse('fitting:result:file_download',
                    args=[fittingresult_version.fittingresult.pk, fittingresult_version.pk, filename])
        )

        assert response.status_code == 200
        assert response.content == b'1,1\n'
        assert response['Content-Disposition'] == (
            'attachment; filename=' + filename
        )
        assert response['Content-Type'] == 'text/csv'

    def test_disallows_non_local_files(self, client, archive_file_path, fittingresult_version):
        fittingresult_version.mkdir()
        shutil.copyfile(archive_file_path, str(fittingresult_version.archive_path))

        for filename in ['/etc/passwd', '../../../pytest.ini']:
            response = client.get(
                '/fitting/results/%d/versions/%d/download/%s' % (
                    fittingresult_version.fittingresult.pk, fittingresult_version.pk, filename)
            )
            assert response.status_code == 404


@pytest.mark.django_db
class TestFittingResultVersionJsonView:
    def test_fittingresult_json(self, client, logged_in_user, fittingresult_version):
        version = fittingresult_version

        version.author.full_name = 'test user'
        version.author.save()
        version.status = 'SUCCESS'

        response = client.get(
            ('/fitting/results/%d/versions/%d/files.json' % (version.fittingresult.pk, version.pk))
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
        assert ver['fittingResultId'] == version.fittingresult.id
        assert ver['version'] == version.id
        assert ver['files'] == []
        assert ver['numFiles'] == 0
        assert ver['download_url'] == (
            '/fitting/results/%d/versions/%d/archive' % (version.fittingresult.pk, version.pk)
        )

    def test_file_json(self, client, archive_file_path, fittingresult_version):
        version = fittingresult_version
        version.author.full_name = 'test user'
        version.author.save()
        version.mkdir()
        shutil.copyfile(archive_file_path, str(version.archive_path))

        response = client.get(
            ('/fitting/results/%d/versions/%d/files.json' % (version.fittingresult.pk, version.pk))
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
            '/fitting/results/%d/versions/%d/download/stdout.txt' % (version.fittingresult.pk, version.pk)
        )


@pytest.mark.django_db
class TestFittingResultDeletion:
    def test_owner_can_delete_fittingresult(
        self, logged_in_user, client, fittingresult_with_result
    ):
        fittingresult = fittingresult_with_result.fittingresult
        fittingresult.author = logged_in_user
        fittingresult.save()
        exp_ver_path = fittingresult_with_result.abs_path
        assert FittingResult.objects.filter(pk=fittingresult.pk).exists()

        response = client.post('/fitting/results/%d/delete' % fittingresult.pk)

        assert response.status_code == 302
        assert response.url == '/experiments/?show_fits=true'

        assert not FittingResult.objects.filter(pk=fittingresult.pk).exists()
        assert not exp_ver_path.exists()

    @pytest.mark.usefixtures('logged_in_user')
    def test_non_owner_cannot_delete_fittingresult(
        self, other_user, client, fittingresult_with_result
    ):
        fittingresult = fittingresult_with_result.fittingresult
        fittingresult.author = other_user
        fittingresult.save()
        exp_ver_path = fittingresult_with_result.abs_path

        response = client.post('/fitting/results/%d/delete' % fittingresult.pk)

        assert response.status_code == 403
        assert FittingResult.objects.filter(pk=fittingresult.pk).exists()
        assert exp_ver_path.exists()

    def test_owner_can_delete_fittingresult_version(
        self, logged_in_user, client, fittingresult_with_result
    ):
        fittingresult = fittingresult_with_result.fittingresult
        fittingresult_with_result.author = logged_in_user
        fittingresult_with_result.save()
        exp_ver_path = fittingresult_with_result.abs_path

        response = client.post(
            '/fitting/results/%d/versions/%d/delete' %
            (fittingresult.pk, fittingresult_with_result.pk))

        assert response.status_code == 302
        assert response.url == '/fitting/results/%d/versions/' % fittingresult.pk

        assert not FittingResultVersion.objects.filter(pk=fittingresult_with_result.pk).exists()
        assert not exp_ver_path.exists()
        assert FittingResult.objects.filter(pk=fittingresult.pk).exists()

    @pytest.mark.usefixtures('logged_in_user')
    def test_non_owner_cannot_delete_fittingresult_version(
        self, other_user, client, fittingresult_with_result
    ):
        fittingresult = fittingresult_with_result.fittingresult
        fittingresult_with_result.author = other_user
        fittingresult_with_result.save()
        exp_ver_path = fittingresult_with_result.abs_path

        response = client.post(
            '/fitting/results/%d/versions/%d/delete' %
            (fittingresult.pk, fittingresult_with_result.pk))

        assert response.status_code == 403
        assert FittingResultVersion.objects.filter(pk=fittingresult_with_result.pk).exists()
        assert FittingResult.objects.filter(pk=fittingresult.pk).exists()
        assert exp_ver_path.exists()
