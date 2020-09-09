import json
import shutil
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from django.core.urlresolvers import reverse
from django.utils.dateparse import parse_datetime
from pytest_django.asserts import assertContains, assertTemplateUsed

from core import recipes
from fitting.models import FittingResult, FittingResultVersion
from repocache.populate import populate_entity_cache


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


@pytest.mark.django_db
class TestFittingResultComparisonView:
    def test_compare_fittingresults(self, client, fittingresult_version, helpers):
        fit = fittingresult_version.fittingresult
        protocol = recipes.protocol.make()
        protocol_commit = helpers.add_version(protocol, visibility='public')

        version2 = recipes.fittingresult_version.make(
            status='SUCCESS',
            fittingresult__model=fit.model,
            fittingresult__model_version=fit.model_version,
            fittingresult__protocol=protocol,
            fittingresult__protocol_version=protocol.repocache.get_version(protocol_commit.sha),
            fittingresult__fittingspec=fit.fittingspec,
            fittingresult__fittingspec_version=fit.fittingspec_version,
            fittingresult__dataset=fit.dataset,
        )

        response = client.get(
            ('/fitting/results/compare/%d/%d' % (fittingresult_version.id, version2.id))
        )

        assert response.status_code == 200
        assert set(response.context['fittingresult_versions']) == {
            fittingresult_version, version2
        }

    def test_only_compare_visible_fittingresults(self, client, fittingresult_version, helpers):
        ver1 = fittingresult_version
        fit = ver1.fittingresult

        proto = recipes.protocol.make()
        proto_commit = helpers.add_version(proto, visibility='private')
        ver2 = recipes.fittingresult_version.make(
            status='SUCCESS',
            fittingresult__model=fit.model,
            fittingresult__model_version=fit.model_version,
            fittingresult__protocol=proto,
            fittingresult__protocol_version=proto.repocache.get_version(proto_commit.sha),
            fittingresult__fittingspec=fit.fittingspec,
            fittingresult__fittingspec_version=fit.fittingspec_version,
            fittingresult__dataset=fit.dataset,
        )

        response = client.get(
            ('/fitting/results/compare/%d/%d' % (ver1.id, ver2.id))
        )

        assert response.status_code == 200
        assert set(response.context['fittingresult_versions']) == {ver1}

        assert len(response.context['ERROR_MESSAGES']) == 1

    def test_no_visible_fittingresults(self, client, fittingresult_version):
        proto = fittingresult_version.fittingresult.protocol
        proto.set_version_visibility('latest', 'private')
        fittingresult_version.fittingresult.protocol_version.refresh_from_db()
        assert fittingresult_version.visibility == 'private'

        response = client.get('/fitting/results/compare/%d' % (fittingresult_version.id))

        assert response.status_code == 200
        assert len(response.context['fittingresult_versions']) == 0


@pytest.mark.django_db
class TestFittingResultComparisonJsonView:
    def test_compare_fittingresults(self, client, fittingresult_version, helpers):
        fitres = fittingresult_version.fittingresult
        protocol = recipes.protocol.make()
        protocol_commit = helpers.add_version(protocol, visibility='public')
        fitres.protocol.repo.tag('v1')
        populate_entity_cache(fitres.protocol)

        version2 = recipes.fittingresult_version.make(
            status='SUCCESS',
            fittingresult__model=fitres.model,
            fittingresult__model_version=fitres.model_version,
            fittingresult__protocol=protocol,
            fittingresult__protocol_version=protocol.repocache.get_version(protocol_commit.sha),
            fittingresult__fittingspec=fitres.fittingspec,
            fittingresult__fittingspec_version=fitres.fittingspec_version,
            fittingresult__dataset=fitres.dataset,
        )

        response = client.get(
            ('/fitting/results/compare/%d/%d/info' % (fittingresult_version.id, version2.id))
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        versions = data['getEntityInfos']['entities']
        assert versions[0]['versionId'] == fittingresult_version.id
        assert versions[1]['versionId'] == version2.id
        assert versions[0]['modelName'] == fitres.model.name
        assert versions[0]['modelVersion'] == fitres.model_version.sha
        assert versions[0]['protoName'] == fitres.protocol.name
        assert versions[0]['protoVersion'] == 'v1'
        assert versions[0]['fittingSpecName'] == fitres.fittingspec.name
        assert versions[0]['fittingSpecVersion'] == fitres.fittingspec_version.sha
        assert versions[0]['datasetName'] == fitres.dataset.name
        assert versions[0]['name'] == fitres.name
        assert versions[0]['runNumber'] == 1

    def test_only_compare_visible_fittingresults(self, client, fittingresult_version, helpers):
        ver1 = fittingresult_version
        fitres = ver1.fittingresult

        proto = recipes.protocol.make()
        proto_commit = helpers.add_version(proto, visibility='private')
        ver2 = recipes.fittingresult_version.make(
            status='SUCCESS',
            fittingresult__model=fitres.model,
            fittingresult__model_version=fitres.model_version,
            fittingresult__protocol=proto,
            fittingresult__protocol_version=proto.repocache.get_version(proto_commit.sha),
            fittingresult__fittingspec=fitres.fittingspec,
            fittingresult__fittingspec_version=fitres.fittingspec_version,
            fittingresult__dataset=fitres.dataset,
        )

        response = client.get(
            ('/fitting/results/compare/%d/%d/info' % (ver1.id, ver2.id))
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        versions = data['getEntityInfos']['entities']
        assert len(versions) == 1
        assert versions[0]['versionId'] == ver1.id

    def test_file_json(self, client, archive_file_path, helpers, fittingresult_version):
        fittingresult_version.author.full_name = 'test user'
        fittingresult_version.author.save()
        fittingresult_version.mkdir()
        shutil.copyfile(archive_file_path, str(fittingresult_version.archive_path))
        fitres = fittingresult_version.fittingresult
        fitres.model.set_version_visibility('latest', 'public')
        fitres.protocol.set_version_visibility('latest', 'public')

        protocol = recipes.protocol.make()
        protocol_commit = helpers.add_version(protocol, visibility='public')
        version2 = recipes.fittingresult_version.make(
            status='SUCCESS',
            fittingresult__model=fitres.model,
            fittingresult__model_version=fitres.model.repocache.get_version(fitres.model_version.sha),
            fittingresult__protocol=protocol,
            fittingresult__protocol_version=protocol.repocache.get_version(protocol_commit.sha),
        )
        version2.mkdir()
        shutil.copyfile(archive_file_path, str(version2.archive_path))

        response = client.get(
            ('/fitting/results/compare/%d/%d/info' % (fittingresult_version.pk, version2.pk))
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
            '/fitting/results/%d/versions/%d/download/stdout.txt' % (fitres.pk, fittingresult_version.pk)
        )

    def test_empty_fittingresult_list(self, client, fittingresult_version):
        response = client.get('/fitting/results/compare/info')

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert len(data['getEntityInfos']['entities']) == 0
