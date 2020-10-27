import json
import shutil
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.urlresolvers import reverse
from django.utils.dateparse import parse_datetime
from pytest_django.asserts import assertContains, assertTemplateUsed

from core import recipes
from fitting.models import FittingResult, FittingResultVersion, FittingSpec
from repocache.populate import populate_entity_cache


@pytest.fixture
def archive_file_path():
    return str(Path(__file__).absolute().parent.joinpath('./test.omex'))


def make_fittingresult(model, model_version, fittingspec, dataset):
    """Create an experiment in the DB with a single version."""
    fit = recipes.fittingresult.make(
        model=model, model_version=model_version,
        protocol=dataset.protocol,
        protocol_version=dataset.protocol.repocache.latest_version,
        fittingspec=fittingspec,
        fittingspec_version=fittingspec.repocache.latest_version,
        dataset=dataset,
    )
    recipes.fittingresult_version.make(fittingresult=fit)
    return fit


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


@pytest.mark.django_db
class TestCreateFittingResultView:
    def test_requires_login(self, client):
        response = client.get('/fitting/results/new')
        assert response.status_code == 302

    def test_requires_permission(self, client, logged_in_user):
        response = client.get('/fitting/results/new')
        assert response.status_code == 302

    def test_basic_page(self, client, fits_user):
        response = client.get('/fitting/results/new')
        assert response.status_code == 200
        assert 'form' in response.context

    def test_with_preselected_model(self, client, fits_user, public_model):
        response = client.get('/fitting/results/new', {'model': public_model.pk})
        assert response.status_code == 200
        assert response.context['form'].initial['model'] == public_model

    def test_with_preselected_protocol(self, client, fits_user, public_protocol):
        response = client.get('/fitting/results/new', {'protocol': public_protocol.pk})
        assert response.status_code == 200
        assert response.context['form'].initial['protocol'] == public_protocol

    def test_with_preselected_fittingspec(self, client, fits_user, public_fittingspec):
        response = client.get('/fitting/results/new', {'fittingspec': public_fittingspec.pk})
        assert response.status_code == 200
        assert response.context['form'].initial['fittingspec'] == public_fittingspec

    def test_with_preselected_dataset(self, client, fits_user, public_dataset):
        response = client.get('/fitting/results/new', {'dataset': public_dataset.pk})
        assert response.status_code == 200
        assert response.context['form'].initial['dataset'] == public_dataset

    def test_with_preselected_model_version(self, client, fits_user, public_model):
        version = public_model.repocache.latest_version
        response = client.get('/fitting/results/new', {'model_version': version.pk})
        assert response.status_code == 200
        assert response.context['form'].initial['model'] == public_model
        assert response.context['form'].initial['model_version'] == version

    def test_with_preselected_model_version_by_sha(self, client, fits_user, public_model):
        version = public_model.repocache.latest_version
        response = client.get('/fitting/results/new', {'model_version': version.sha})
        assert response.status_code == 200
        assert response.context['form'].initial['model'] == public_model
        assert response.context['form'].initial['model_version'] == version

    def test_with_preselected_protocol_version(self, client, fits_user, public_protocol):
        version = public_protocol.repocache.latest_version
        response = client.get('/fitting/results/new', {'protocol_version': version.pk})
        assert response.status_code == 200
        assert response.context['form'].initial['protocol'] == public_protocol
        assert response.context['form'].initial['protocol_version'] == version

    def test_with_preselected_protocol_version_by_sha(self, client, fits_user, public_protocol):
        version = public_protocol.repocache.latest_version
        response = client.get('/fitting/results/new', {'protocol_version': version.sha})
        assert response.status_code == 200
        assert response.context['form'].initial['protocol'] == public_protocol
        assert response.context['form'].initial['protocol_version'] == version

    def test_with_preselected_fittingspec_version(self, client, fits_user, public_fittingspec):
        version = public_fittingspec.repocache.latest_version
        response = client.get('/fitting/results/new', {'fittingspec_version': version.pk})
        assert response.status_code == 200
        assert response.context['form'].initial['fittingspec'] == public_fittingspec
        assert response.context['form'].initial['fittingspec_version'] == version

    def test_with_preselected_fittingspec_version_by_sha(self, client, fits_user, public_fittingspec):
        version = public_fittingspec.repocache.latest_version
        response = client.get('/fitting/results/new', {'fittingspec_version': version.sha})
        assert response.status_code == 200
        assert response.context['form'].initial['fittingspec'] == public_fittingspec
        assert response.context['form'].initial['fittingspec_version'] == version

    def test_with_non_visible_model(self, client, fits_user, private_model):
        response = client.get('/fitting/results/new', {'model': private_model.pk})
        assert response.status_code == 404

    def test_with_non_visible_model_version(self, client, fits_user, private_model):
        version = private_model.repocache.latest_version
        response = client.get('/fitting/results/new', {'model_version': version.pk})
        assert response.status_code == 404

    def test_with_non_visible_protocol(self, client, fits_user, private_protocol):
        response = client.get('/fitting/results/new', {'protocol': private_protocol.pk})
        assert response.status_code == 404

    def test_with_non_visible_protocol_version(self, client, fits_user, private_protocol):
        version = private_protocol.repocache.latest_version
        response = client.get('/fitting/results/new', {'protocol_version': version.pk})
        assert response.status_code == 404

    def test_with_non_visible_fittingspec(self, client, fits_user, private_fittingspec):
        response = client.get('/fitting/results/new', {'fittingspec': private_fittingspec.pk})
        assert response.status_code == 404

    def test_with_non_visible_fittingspec_version(self, client, fits_user, private_fittingspec):
        version = private_fittingspec.repocache.latest_version
        response = client.get('/fitting/results/new', {'fittingspec_version': version.pk})
        assert response.status_code == 404

    def test_with_non_visible_dataset(self, client, fits_user, private_dataset):
        response = client.get('/fitting/results/new', {'dataset': private_dataset.pk})
        assert response.status_code == 404

    @patch('fitting.views.submit_fitting')
    def test_submits_to_backend(self, mock_submit, client, fits_user, public_model, public_protocol,
                                public_fittingspec, public_dataset, helpers):
        model_version = public_model.repocache.latest_version
        protocol_version = public_protocol.repocache.latest_version
        fittingspec_version = public_fittingspec.repocache.latest_version
        helpers.link_to_protocol(public_protocol, public_fittingspec, public_dataset)

        runnable = recipes.fittingresult_version.make()
        mock_submit.return_value = (runnable, False)

        response = client.post('/fitting/results/new', {
            'model': public_model.pk,
            'model_version': model_version.pk,
            'protocol': public_protocol.pk,
            'protocol_version': protocol_version.pk,
            'fittingspec': public_fittingspec.pk,
            'fittingspec_version': fittingspec_version.pk,
            'dataset': public_dataset.pk,
        })

        assert response.status_code == 302
        mock_submit.assert_called_with(
            model_version,
            protocol_version,
            fittingspec_version,
            public_dataset, fits_user, True
        )

        assert response.url == '/fitting/results/%d/versions/%d' % (runnable.fittingresult.pk, runnable.pk)


@pytest.mark.django_db
class TestFittingResultFilterJsonView:
    def test_requires_login(self, client):
        response = client.get('/fitting/results/new/filter')
        assert response.status_code == 302

    def test_requires_permission(self, client, logged_in_user):
        response = client.get('/fitting/results/new/filter')
        assert response.status_code == 302

    def test_all_models_and_versions(self, client, fits_user, helpers):
        model1 = recipes.model.make()
        model2 = recipes.model.make()
        m1v1 = helpers.add_cached_version(model1, visibility='public')
        m2v1 = helpers.add_cached_version(model2, visibility='public')

        response = client.get('/fitting/results/new/filter', {})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        assert 'fittingResultOptions' in data
        options = data['fittingResultOptions']
        assert set(options['models']) == {model1.id, model2.id}
        assert set(options['model_versions']) == {m1v1.id, m2v1.id}

    def test_model_and_version_must_be_visible_to_user(self, client, fits_user, helpers):
        model1 = recipes.model.make()
        model2 = recipes.model.make()
        m1v1 = helpers.add_cached_version(model1, visibility='public')
        m2v1 = helpers.add_cached_version(model2, visibility='private')  # noqa: F841

        response = client.get('/fitting/results/new/filter', {})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        assert 'fittingResultOptions' in data
        options = data['fittingResultOptions']
        assert set(options['models']) == {model1.id}
        assert set(options['model_versions']) == {m1v1.id}

    def test_all_protocols_and_versions(self, client, fits_user, helpers):
        protocol1 = recipes.protocol.make()
        protocol2 = recipes.protocol.make()
        p1v1 = helpers.add_cached_version(protocol1, visibility='public')
        p2v1 = helpers.add_cached_version(protocol2, visibility='public')

        response = client.get('/fitting/results/new/filter', {})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        options = data['fittingResultOptions']
        assert set(options['protocols']) == {protocol1.id, protocol2.id}
        assert set(options['protocol_versions']) == {p1v1.id, p2v1.id}

    def test_protocol_and_version_must_be_visible_to_user(self, client, fits_user, helpers):
        protocol1 = recipes.protocol.make()
        protocol2 = recipes.protocol.make()
        p1v1 = helpers.add_cached_version(protocol1, visibility='public')
        p2v1 = helpers.add_cached_version(protocol2, visibility='private')  # noqa: F841

        response = client.get('/fitting/results/new/filter', {})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        assert 'fittingResultOptions' in data
        options = data['fittingResultOptions']
        assert set(options['protocols']) == {protocol1.id}
        assert set(options['protocol_versions']) == {p1v1.id}

    def test_all_fittingspecs_and_versions(self, client, fits_user, helpers):
        fittingspec1 = recipes.fittingspec.make()
        fittingspec2 = recipes.fittingspec.make()
        f1v1 = helpers.add_cached_version(fittingspec1, visibility='public')
        f2v1 = helpers.add_cached_version(fittingspec2, visibility='public')

        response = client.get('/fitting/results/new/filter', {})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        options = data['fittingResultOptions']
        assert set(options['fittingspecs']) == {fittingspec1.id, fittingspec2.id}
        assert set(options['fittingspec_versions']) == {f1v1.id, f2v1.id}

    def test_fittingspec_and_version_must_be_visible_to_user(self, client, fits_user, helpers):
        fittingspec1 = recipes.fittingspec.make()
        fittingspec2 = recipes.fittingspec.make()
        p1v1 = helpers.add_cached_version(fittingspec1, visibility='public')
        p2v1 = helpers.add_cached_version(fittingspec2, visibility='private')  # noqa: F841

        response = client.get('/fitting/results/new/filter', {})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        assert 'fittingResultOptions' in data
        options = data['fittingResultOptions']
        assert set(options['fittingspecs']) == {fittingspec1.id}
        assert set(options['fittingspec_versions']) == {p1v1.id}

    def test_all_datasets(self, client, fits_user):
        dataset1 = recipes.dataset.make(visibility='public')
        dataset2 = recipes.dataset.make(visibility='public')

        response = client.get('/fitting/results/new/filter', {})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        options = data['fittingResultOptions']
        assert set(options['datasets']) == {dataset1.id, dataset2.id}

    def test_dataset_must_be_visible_to_user(self, client, fits_user, helpers):
        dataset1 = recipes.dataset.make(visibility='public')
        dataset2 = recipes.dataset.make(visibility='private')  # noqa: F841

        response = client.get('/fitting/results/new/filter', {})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        assert 'fittingResultOptions' in data
        options = data['fittingResultOptions']
        assert set(options['datasets']) == {dataset1.id}

    def test_versions_restricted_when_model_selected(self, client, fits_user, helpers):
        model1 = recipes.model.make()
        model2 = recipes.model.make()
        m1v1 = helpers.add_cached_version(model1, visibility='public')
        m2v1 = helpers.add_cached_version(model2, visibility='public')  # noqa: F841

        response = client.get('/fitting/results/new/filter', {'model': model1.id})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        options = data['fittingResultOptions']
        assert options['models'] == [model1.id, model2.id]
        assert options['model_versions'] == [m1v1.id]

    def test_versions_restricted_when_protocol_selected(self, client, fits_user, helpers):
        protocol1 = recipes.protocol.make()
        protocol2 = recipes.protocol.make()
        p1v1 = helpers.add_cached_version(protocol1, visibility='public')
        p2v1 = helpers.add_cached_version(protocol2, visibility='public')  # noqa: F841

        response = client.get('/fitting/results/new/filter', {'protocol': protocol1.id})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        options = data['fittingResultOptions']
        assert options['protocols'] == [protocol1.id, protocol2.id]
        assert options['protocol_versions'] == [p1v1.id]

    def test_versions_restricted_when_fittingspec_selected(self, client, fits_user, helpers):
        fittingspec1 = recipes.fittingspec.make()
        fittingspec2 = recipes.fittingspec.make()
        f1v1 = helpers.add_cached_version(fittingspec1, visibility='public')
        f2v1 = helpers.add_cached_version(fittingspec2, visibility='public')  # noqa: F841

        response = client.get('/fitting/results/new/filter', {'fittingspec': fittingspec1.id})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        options = data['fittingResultOptions']
        assert options['fittingspecs'] == [fittingspec1.id, fittingspec2.id]
        assert options['fittingspec_versions'] == [f1v1.id]

    def test_dataset_and_fittingspec_restricted_when_protocol_selected(self, client, fits_user, helpers):
        protocol = recipes.protocol.make()
        helpers.add_cached_version(protocol, visibility='public')
        fittingspec1 = recipes.fittingspec.make(protocol=protocol)
        fittingspec2 = recipes.fittingspec.make()
        f1v1 = helpers.add_cached_version(fittingspec1, visibility='public')
        f2v1 = helpers.add_cached_version(fittingspec2, visibility='public')  # noqa: F841
        dataset1 = recipes.dataset.make(protocol=protocol, visibility='public')
        dataset2 = recipes.dataset.make(visibility='public')  # noqa: F841

        response = client.get('/fitting/results/new/filter', {'protocol': protocol.id})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        options = data['fittingResultOptions']
        assert options['datasets'] == [dataset1.id]
        assert options['fittingspecs'] == [fittingspec1.id]
        assert options['fittingspec_versions'] == [f1v1.id]

    def test_protocol_and_fittingspec_restricted_when_dataset_selected(self, client, fits_user, helpers):
        protocol1 = recipes.protocol.make()
        protocol2 = recipes.protocol.make()
        p1v1 = helpers.add_cached_version(protocol1, visibility='public')
        p2v1 = helpers.add_cached_version(protocol2, visibility='public')  # noqa: F841
        fittingspec1 = recipes.fittingspec.make(protocol=protocol1)
        fittingspec2 = recipes.fittingspec.make()
        f1v1 = helpers.add_cached_version(fittingspec1, visibility='public')
        f2v1 = helpers.add_cached_version(fittingspec2, visibility='public')  # noqa: F841

        dataset = recipes.dataset.make(protocol=protocol1, visibility='public')

        response = client.get('/fitting/results/new/filter', {'dataset': dataset.id})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        options = data['fittingResultOptions']
        assert options['protocols'] == [protocol1.id]
        assert options['protocol_versions'] == [p1v1.id]
        assert options['fittingspecs'] == [fittingspec1.id]
        assert options['fittingspec_versions'] == [f1v1.id]

    def test_protocol_and_dataset_restricted_when_fittingspec_selected(self, client, fits_user, helpers):
        protocol1 = recipes.protocol.make()
        protocol2 = recipes.protocol.make()
        p1v1 = helpers.add_cached_version(protocol1, visibility='public')
        p2v1 = helpers.add_cached_version(protocol2, visibility='public')  # noqa: F841
        dataset1 = recipes.dataset.make(protocol=protocol1, visibility='public')
        dataset2 = recipes.dataset.make(visibility='public')  # noqa: F841

        fittingspec = recipes.fittingspec.make(protocol=protocol1)

        response = client.get('/fitting/results/new/filter', {'fittingspec': fittingspec.id})
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        options = data['fittingResultOptions']
        assert options['protocols'] == [protocol1.id]
        assert options['protocol_versions'] == [p1v1.id]
        assert options['datasets'] == [dataset1.id]


@pytest.mark.django_db
class TestFittingSpecRenaming:
    def test_fittingspec_renaming_success(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_fittingspec')
        fittingspec = recipes.fittingspec.make(author=logged_in_user)
        assert fittingspec.name == 'my spec1'

        response = client.post(
            '/fitting/specs/%d/rename' % fittingspec.pk,
            data={
                'name': 'new name'
            })
        assert response.status_code == 302
        fittingspec2 = FittingSpec.objects.first()
        assert fittingspec2.name == "new name"

    def test_fittingspec_renaming_different_users_succeeds(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_fittingspec')
        fittingspec = recipes.fittingspec.make(author=logged_in_user)

        fittingspec2 = recipes.fittingspec.make(name='test fittingspec 2')
        assert fittingspec.name == 'my spec1'
        assert fittingspec2.name == 'test fittingspec 2'

        response = client.post(
            '/fitting/specs/%d/rename' % fittingspec.pk,
            data={
                'name': 'test fittingspec 2'
            })
        assert response.status_code == 302
        fittingspec = FittingSpec.objects.first()
        assert fittingspec.name == 'test fittingspec 2'

    def test_dataset_renaming_same_users_fails(self, client, logged_in_user, helpers):
        helpers.add_permission(logged_in_user, 'create_fittingspec')
        fittingspec = recipes.fittingspec.make(author=logged_in_user)
        fittingspec2 = recipes.fittingspec.make(author=logged_in_user, name='test fittingspec 2')
        assert fittingspec.name == 'my spec1'
        assert fittingspec2.name == 'test fittingspec 2'

        response = client.post(
            '/fitting/specs/%d/rename' % fittingspec.pk,
            data={
                'name': 'test fittingspec 2'
            })
        assert response.status_code == 200
        fittingspec = FittingSpec.objects.first()
        assert fittingspec.name == 'my spec1'


@pytest.mark.django_db
class TestRerunFittingView:
    def test_requires_login(self, client):
        response = client.post('/fitting/results/rerun')
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert not data['newExperiment']['response']
        assert (
            data['newExperiment']['responseText'] ==
            'You are not allowed to run fitting experiments'
        )

    def test_requires_permission(self, client, logged_in_user):
        response = client.post('/fitting/results/rerun')
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        assert not data['newExperiment']['response']
        assert (
            data['newExperiment']['responseText'] ==
            'You are not allowed to run fitting experiments'
        )

    def test_raises_error_if_no_rerun_id(self, client, fits_user):
        response = client.post('/fitting/results/rerun')
        assert response.status_code == 200

        data = json.loads(response.content.decode())
        assert not data['newExperiment']['response']
        assert (
            data['newExperiment']['responseText'] ==
            'You must specify a fitting experiment to rerun'
        )

    @patch('fitting.views.submit_fitting')
    def test_rerun_experiment(
        self, mock_submit, client, fits_user, fittingresult_version
    ):

        fittingresult = fittingresult_version.fittingresult
        new_runnable = recipes.fittingresult_version.make(fittingresult=fittingresult)
        mock_submit.return_value = (new_runnable, True)

        response = client.post(
            '/fitting/results/rerun',
            {
                'rerun': fittingresult_version.pk,
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        url = '/fitting/results/%d/versions/%d' % (fittingresult.id, new_runnable.id)

        assert 'newExperiment' in data
        assert data['newExperiment']['expId'] == fittingresult.id
        assert data['newExperiment']['versionId'] == new_runnable.id
        assert data['newExperiment']['url'] == url
        assert data['newExperiment']['expName'] == fittingresult.name
        assert data['newExperiment']['status'] == 'QUEUED'
        assert data['newExperiment']['response'] is True
        message = data['newExperiment']['responseText']
        assert url in message
        assert fittingresult.name in message
        assert 'submitted to the queue' in message
        assert 'Experiment' in message

    @patch('fitting.views.submit_fitting')
    def test_rerun_experiment_with_failure(
        self, mock_submit, client, fits_user, fittingresult_version
    ):

        fittingresult = fittingresult_version.fittingresult
        new_runnable = recipes.fittingresult_version.make(
            fittingresult=fittingresult, status='FAILED', return_text='something failed'
        )
        mock_submit.return_value = (new_runnable, True)

        response = client.post(
            '/fitting/results/rerun',
            {
                'rerun': fittingresult_version.pk,
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        url = '/fitting/results/%d/versions/%d' % (fittingresult.id, new_runnable.id)

        assert 'newExperiment' in data
        assert data['newExperiment']['expId'] == fittingresult.id
        assert data['newExperiment']['versionId'] == new_runnable.id
        assert data['newExperiment']['url'] == url
        assert data['newExperiment']['expName'] == fittingresult.name
        assert data['newExperiment']['status'] == 'FAILED'
        assert data['newExperiment']['response'] is False
        message = data['newExperiment']['responseText']
        assert url in message
        assert fittingresult.name in message
        assert 'could not be run: something failed' in message
        assert 'Experiment' in message


@pytest.mark.django_db
class TestTransferOwner:
    def test_fittingspec_transfer_success(self, client, logged_in_user, other_user, helpers):
        helpers.add_permission(logged_in_user, 'create_fittingspec')
        fittingspec = recipes.fittingspec.make(author=logged_in_user)
        oldpath = fittingspec.repo_abs_path

        assert fittingspec.author.email == 'test@example.com'
        response = client.post(
            '/fitting/specs/%d/transfer' % fittingspec.pk,
            data={
                'email': other_user.email,
            },
        )
        assert response.status_code == 302
        fittingspec.refresh_from_db()
        assert fittingspec.author == other_user
        assert not oldpath.exists()
        assert fittingspec.repo_abs_path.exists()


@pytest.mark.django_db
class TestFittingSpecResultsMatrixView:

    @pytest.mark.parametrize("url", [
        '/fitting/specs/%d/results/',
        '/fitting/specs/%d/results/mine',
        '/fitting/specs/%d/results/public',
        '/fitting/specs/%d/results/all',
        '/fitting/specs/%d/results/public/models/1/2',
        '/fitting/specs/%d/results/all/datasets/1/2',
        '/fitting/specs/%d/results/models/1/2',
        '/fitting/specs/%d/results/models/1/2/datasets/3/4',
        '/fitting/specs/%d/results/datasets/1/2',
        '/fitting/specs/%d/results/models/1/versions/abc/def',
        '/fitting/specs/%d/results/models/1/versions/*',
        '/fitting/specs/%d/results/models/1/versions/abc/def/datasets/3/4',
    ])
    def test_urls(self, client, url, public_fittingspec):
        """
        This is a dumb page that doesn't actually load any data, so we just
        check that the URLs are working.
        """
        response = client.get(url % public_fittingspec.id)
        assert response.status_code == 200

    def test_matrix_page_for_fitting_spec(self, client, public_fittingspec):
        response = client.get('/fitting/specs/%d/results' % public_fittingspec.pk)
        assert response.status_code == 200
        assert response.context['fittingspec'] == public_fittingspec

    def test_raises_404_for_non_visible_spec(self, client, private_fittingspec):
        response = client.get('/fitting/specs/%d/results' % private_fittingspec.pk)
        assert response.status_code == 404


@pytest.mark.django_db
class TestFittingSpecResultsMatrixJsonView:
    def test_matrix_json_for_fitting_spec(self, client, public_fittingspec):
        response = client.get('/fitting/specs/%d/results/matrix' % public_fittingspec.pk)
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

    def test_raises_404_for_non_visible_spec(self, client, private_fittingspec):
        response = client.get('/fitting/specs/%d/results/matrix' % private_fittingspec.pk)
        assert response.status_code == 404

    def test_matrix_json(self, client, quick_fittingresult_version):
        fit = quick_fittingresult_version.fittingresult

        response = client.get('/fitting/specs/%d/results/matrix?subset=all' % fit.fittingspec.pk)
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert len(data['getMatrix']['rows']) == 1
        assert str(fit.model_version.sha) in data['getMatrix']['rows']
        assert len(data['getMatrix']['columns']) == 1
        assert str(fit.dataset.id) in data['getMatrix']['columns']
        assert len(data['getMatrix']['experiments']) == 1
        assert str(fit.pk) in data['getMatrix']['experiments']

        fit_data = data['getMatrix']['experiments'][str(fit.pk)]
        assert fit_data['id'] == quick_fittingresult_version.id
        assert fit_data['entity_id'] == fit.id
        assert fit_data['latestResult'] == quick_fittingresult_version.status
        assert fit_data['dataset']['id'] == fit.dataset.id
        assert '/fitting/results/%d/versions/%d' % (fit.id, quick_fittingresult_version.id) in fit_data['url']

    def test_anonymous_cannot_see_private_data(self, client, quick_fittingresult_version):
        fit = quick_fittingresult_version.fittingresult
        model_version = fit.model_version
        model_version.visibility = 'private'
        model_version.save()

        response = client.get('/fitting/specs/%d/results/matrix?subset=all' % fit.fittingspec.pk)
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data
        assert len(data['getMatrix']['rows']) == 0
        assert len(data['getMatrix']['columns']) == 1
        assert len(data['getMatrix']['experiments']) == 0

    def test_view_mine_with_moderated_flags(
        self, client, helpers, logged_in_user,
        moderated_model, public_fittingspec, public_protocol,
    ):
        my_model = recipes.model.make(author=logged_in_user)
        my_model_version = helpers.add_fake_version(my_model, visibility='private')

        my_moderated_model = recipes.model.make(author=logged_in_user)
        helpers.add_fake_version(my_moderated_model, visibility='moderated')

        my_dataset = recipes.dataset.make(
            author=logged_in_user, protocol=public_protocol, visibility='private'
        )
        moderated_dataset = recipes.dataset.make(
            protocol=public_protocol, visibility='moderated'
        )
        my_moderated_dataset = recipes.dataset.make(
            author=logged_in_user, protocol=public_protocol, visibility='moderated'
        )

        my_version = make_fittingresult(my_model, my_model_version, public_fittingspec, my_dataset)

        with_moderated_model = make_fittingresult(
            moderated_model,
            moderated_model.repocache.latest_version,
            public_fittingspec,
            my_dataset,
        )
        with_moderated_dataset = make_fittingresult(
            my_model,
            my_model_version,
            public_fittingspec,
            moderated_dataset,
        )
        with_my_moderated_model = make_fittingresult(
            my_moderated_model,
            my_moderated_model.repocache.latest_version,
            public_fittingspec,
            my_dataset,
        )
        with_my_moderated_dataset = make_fittingresult(
            my_model,
            my_model_version,
            public_fittingspec,
            my_moderated_dataset,
        )

        matrix_url = '/fitting/specs/%d/results/matrix' % public_fittingspec.pk

        # All my fittingresults plus ones involving moderated entities
        response = client.get(matrix_url + '?subset=mine')
        data = json.loads(response.content.decode())
        fittingresult_ids = set(data['getMatrix']['experiments'])
        assert fittingresult_ids == {
            str(my_version.pk),
            str(with_moderated_model.pk),
            str(with_moderated_dataset.pk),
            str(with_my_moderated_model.pk),
            str(with_my_moderated_dataset.pk),
        }

        # Exclude those involving moderated datasets
        response = client.get(matrix_url + '?subset=mine&moderated-datasets=false')
        data = json.loads(response.content.decode())
        fittingresult_ids = set(data['getMatrix']['experiments'])
        assert fittingresult_ids == {
            str(my_version.pk),
            str(with_moderated_model.pk),
            str(with_my_moderated_model.pk),
        }

        # Exclude those involving moderated models
        response = client.get(matrix_url + '?subset=mine&moderated-models=false')
        data = json.loads(response.content.decode())
        fittingresult_ids = set(data['getMatrix']['experiments'])
        assert fittingresult_ids == {
            str(my_version.pk),
            str(with_moderated_dataset.pk),
            str(with_my_moderated_dataset.pk),
        }

        # Don't show anything moderated
        response = client.get(matrix_url + '?subset=mine&moderated-models=false&moderated-datasets=false')
        data = json.loads(response.content.decode())
        fittingresult_ids = set(data['getMatrix']['experiments'])
        assert fittingresult_ids == {
            str(my_version.pk),
        }

    def test_view_mine_empty_for_anonymous(self, client, helpers, quick_fittingresult_version):
        spec = quick_fittingresult_version.fittingresult.fittingspec
        response = client.get('/fitting/specs/%d/results/matrix?subset=mine' % spec.pk)
        data = json.loads(response.content.decode())

        assert len(data['getMatrix']['experiments']) == 0

    def test_view_public(self, client, logged_in_user, other_user, helpers, public_fittingspec, public_protocol):
        my_model_moderated = recipes.model.make(author=logged_in_user)
        my_model_moderated_version = helpers.add_fake_version(my_model_moderated, visibility='moderated')

        my_dataset_private = recipes.dataset.make(author=logged_in_user, visibility='private', protocol=public_protocol)
        my_dataset_public = recipes.dataset.make(author=logged_in_user, visibility='public', protocol=public_protocol)

        # My moderated model with my private dataset: should not be visible
        exp1 = make_fittingresult(
            my_model_moderated, my_model_moderated_version,
            public_fittingspec,
            my_dataset_private,
        )

        # Someone else's public model with my public dataset: should be visible
        # But experiments with newer private versions should not be
        other_model_public = recipes.model.make(author=other_user)
        other_model_public_version = helpers.add_fake_version(other_model_public, visibility='public')
        other_model_second_private_version = helpers.add_fake_version(other_model_public, visibility='private')

        exp2 = make_fittingresult(
            other_model_public, other_model_public_version,
            public_fittingspec,
            my_dataset_public,
        )
        exp2_model_private = make_fittingresult(  # noqa: F841
            other_model_public, other_model_second_private_version,
            public_fittingspec,
            my_dataset_public,
        )
        exp2_dataset_private = make_fittingresult(
            other_model_public, other_model_public_version,
            public_fittingspec,
            my_dataset_private,
        )

        # Someone else's public model and moderated dataset: should be visible
        other_dataset_moderated = recipes.dataset.make(
            author=other_user, visibility='moderated', protocol=public_protocol)
        other_dataset_private = recipes.dataset.make(
            author=other_user, visibility='private', protocol=public_protocol)

        exp3 = make_fittingresult(
            other_model_public, other_model_public_version,
            public_fittingspec,
            other_dataset_moderated,
        )
        exp3_dataset_private = make_fittingresult(  # noqa: F841
            other_model_public, other_model_second_private_version,
            public_fittingspec,
            other_dataset_private,
        )

        # Other's private model, my public dataset: should not be visible
        other_model_private = recipes.model.make(author=other_user)
        other_model_private_version = helpers.add_fake_version(other_model_private, visibility='private')

        exp4 = make_fittingresult(  # noqa: F841
            other_model_private, other_model_private_version,
            public_fittingspec,
            my_dataset_public,
        )
        matrix_url = '/fitting/specs/%d/results/matrix' % public_fittingspec.pk

        response = client.get(matrix_url + '?subset=public')
        data = json.loads(response.content.decode())

        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(exp2.pk),
            str(exp3.pk),
        }

        # If however I ask for what I can see, I get more returned
        response = client.get(matrix_url + '?subset=all')
        data = json.loads(response.content.decode())

        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(exp1.pk),
            str(exp2.pk),
            str(exp2_dataset_private.pk),
            str(exp3.pk),
        }

        # If the other user shares their model with me, I see their later private versions instead
        other_model_public.add_collaborator(logged_in_user)
        response = client.get(matrix_url + '?subset=all')
        data = json.loads(response.content.decode())

        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(exp1.pk),
            str(exp2_model_private.pk),
        }

    def test_view_moderated(self, client, logged_in_user, other_user, helpers, public_fittingspec, public_protocol):
        # My public model with somebody else's public dataset: should not be visible
        my_model_public = recipes.model.make(author=logged_in_user)
        my_model_public_version = helpers.add_fake_version(my_model_public, visibility='public')

        other_dataset_public = recipes.dataset.make(author=other_user, visibility='public', protocol=public_protocol)

        exp1 = make_fittingresult(
            my_model_public, my_model_public_version,
            public_fittingspec,
            other_dataset_public,
        )

        # My public model with somebody else's moderated dataset: should not be visible
        other_dataset_moderated = recipes.dataset.make(
            author=other_user, visibility='moderated', protocol=public_protocol)

        exp2 = make_fittingresult(
            my_model_public, my_model_public_version,
            public_fittingspec,
            other_dataset_moderated
        )

        # Someone else's moderated model and public dataset: should not be visible
        other_model_moderated = recipes.model.make(author=other_user)
        other_model_moderated_version = helpers.add_fake_version(other_model_moderated, visibility='moderated')

        exp3 = make_fittingresult(  # noqa: F841
            other_model_moderated, other_model_moderated_version,
            public_fittingspec,
            other_dataset_public
        )

        # Someone else's moderated model and moderated dataset: should be visible
        exp4 = make_fittingresult(
            other_model_moderated, other_model_moderated_version,
            public_fittingspec,
            other_dataset_moderated,
        )

        # A later public version shouldn't show up
        other_model_second_public_version = helpers.add_fake_version(other_model_moderated, visibility='public')
        exp4_public = make_fittingresult(
            other_model_moderated, other_model_second_public_version,
            public_fittingspec,
            other_dataset_moderated,
        )

        matrix_url = '/fitting/specs/%d/results/matrix' % public_fittingspec.pk

        response = client.get(matrix_url)
        data = json.loads(response.content.decode())

        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(exp4.pk),
        }

        # If however I ask for what I can see, I get experiments with later public versions
        response = client.get(matrix_url + '?subset=all')
        data = json.loads(response.content.decode())

        experiment_ids = set(data['getMatrix']['experiments'])
        assert experiment_ids == {
            str(exp1.pk),
            str(exp2.pk),
            str(exp4_public.pk),
        }

    def test_submatrix(self, client, helpers, public_protocol, quick_fittingresult_version):
        fit = quick_fittingresult_version.fittingresult
        spec = fit.fittingspec
        other_model = recipes.model.make()
        other_model_version = helpers.add_fake_version(other_model, visibility='public')
        other_dataset = recipes.dataset.make(protocol=public_protocol, visibility='public')

        make_fittingresult(other_model, other_model_version, spec, other_dataset)

        # Throw in a non-existent dataset so we can make sure it gets ignored
        non_existent_pk = 0
        response = client.get(
            '/fitting/specs/%d/results/matrix' % spec.pk,
            {
                'subset': 'all',
                'rowIds[]': [fit.model.pk, non_existent_pk],
                'columnIds[]': [fit.dataset.pk, non_existent_pk],
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        models = data['getMatrix']['rows']
        assert len(models) == 1
        assert str(fit.model_version.sha) in models
        assert models[str(fit.model_version.sha)]['id'] == str(fit.model_version.sha)
        assert models[str(fit.model_version.sha)]['entityId'] == fit.model.pk

        columns = data['getMatrix']['columns']
        assert len(columns) == 1
        assert str(fit.dataset.pk) in columns
        assert columns[str(fit.dataset.pk)]['id'] == fit.dataset.pk
        assert columns[str(fit.dataset.pk)]['entityId'] == fit.dataset.pk

        experiments = data['getMatrix']['experiments']
        assert len(experiments) == 1
        assert str(fit.pk) in experiments

    def test_submatrix_with_model_versions(self, client, helpers, quick_fittingresult_version):
        fit = quick_fittingresult_version.fittingresult
        spec = fit.fittingspec
        v1 = fit.model_version
        v2 = helpers.add_fake_version(fit.model, visibility='public')
        helpers.add_fake_version(fit.model, visibility='public')  # v3, not used

        # Add an fittingresult with a different model, which shouldn't appear
        other_model = recipes.model.make()
        other_model_version = helpers.add_fake_version(other_model, 'public')
        make_fittingresult(other_model, other_model_version, spec, fit.dataset)

        response = client.get(
            '/fitting/specs/%d/results/matrix' % spec.pk,
            {
                'subset': 'all',
                'rowIds[]': [fit.model.pk],
                'rowVersions[]': [str(v1.sha), str(v2.sha)],
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert set(data['getMatrix']['rows'].keys()) == {str(v1.sha), str(v2.sha)}
        assert set(data['getMatrix']['experiments'].keys()) == {str(fit.pk)}

    def test_submatrix_with_all_model_versions(self, client, helpers, quick_fittingresult_version):
        fit = quick_fittingresult_version.fittingresult
        spec = fit.fittingspec
        v1 = fit.model_version
        v2 = helpers.add_fake_version(fit.model)
        v3 = helpers.add_fake_version(fit.model)

        fit2 = make_fittingresult(
            fit.model, v2, spec, fit.dataset,
        )

        # Add an experiment with a different model, which shouldn't appear
        other_model = recipes.model.make()
        other_model_version = helpers.add_fake_version(other_model, 'public')
        make_fittingresult(other_model, other_model_version, spec, fit.dataset)

        response = client.get(
            '/fitting/specs/%d/results/matrix' % spec.pk,
            {
                'subset': 'all',
                'rowIds[]': [fit.model.pk],
                'rowVersions[]': '*',
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert set(data['getMatrix']['rows'].keys()) == {str(v1.sha), str(v2.sha), str(v3.sha)}
        assert set(data['getMatrix']['experiments'].keys()) == {str(fit.pk), str(fit2.pk)}

    def test_submatrix_with_too_many_model_ids(self, client, helpers, quick_fittingresult_version):
        fit = quick_fittingresult_version.fittingresult
        spec = fit.fittingspec
        model = recipes.model.make()

        response = client.get(
            '/fitting/specs/%d/results/matrix' % spec.pk,
            {
                'subset': 'all',
                'rowIds[]': [quick_fittingresult_version.fittingresult.model.pk, model.pk],
                'rowVersions[]': '*',
            }
        )

        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert len(data['notifications']['errors']) == 1

    def test_experiment_without_version_is_ignored(
        self, client, public_model, public_protocol, public_fittingspec,
    ):

        dataset = recipes.dataset.make(visibility='public', protocol=public_protocol)
        exp = recipes.fittingresult.make(
            model=public_model,
            model_version=public_model.repocache.latest_version,
            protocol=public_protocol,
            protocol_version=public_protocol.repocache.latest_version,
            fittingspec=public_fittingspec,
            fittingspec_version=public_fittingspec.repocache.latest_version,
            dataset=dataset,
        )

        response = client.get('/fitting/specs/%d/results/matrix?subset=all' % public_fittingspec.pk)
        assert response.status_code == 200
        data = json.loads(response.content.decode())
        assert len(data['getMatrix']['columns']) == 1
        assert len(data['getMatrix']['experiments']) == 0

    def test_old_version_is_hidden(self, client, public_model, fittingresult_version, helpers):
        fit = fittingresult_version.fittingresult

        # Add a new model version without corresponding experiment
        new_version = helpers.add_version(public_model, filename='file2.txt')

        # We should now see this version in the matrix, but no experiments
        response = client.get('/fitting/specs/%d/results/matrix?subset=all' % fit.fittingspec.pk)
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data
        assert str(new_version.sha) in data['getMatrix']['rows']
        assert str(fit.dataset.pk) in data['getMatrix']['columns']
        assert len(data['getMatrix']['experiments']) == 0
