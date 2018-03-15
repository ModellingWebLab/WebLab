import io
import json
import zipfile
from io import BytesIO

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from core import recipes
from entities.models import Entity, ModelEntity, ProtocolEntity


@pytest.fixture
def user(client):
    user = User.objects.create_user(
        email='test@example.com',
        full_name='Test User',
        institution='UCL',
        password='password',
    )
    client.login(username='test@example.com', password='password')
    return user


@pytest.fixture
def other_user():
    return recipes.user.make()


def add_permission(user, perm):
    content_type = ContentType.objects.get_for_model(Entity)
    permission = Permission.objects.get(
        codename=perm,
        content_type=content_type,
    )
    user.user_permissions.add(permission)


@pytest.fixture(autouse=True)
def fake_repo_path(settings, tmpdir):
    settings.REPO_BASE = str(tmpdir)
    return settings.REPO_BASE


@pytest.fixture(autouse=True)
def fake_upload_path(settings, tmpdir):
    settings.MEDIA_ROOT = str(tmpdir)
    return settings.MEDIA_ROOT


def add_version(entity, filename='file1.txt', tag_name=None):
    """Add a single commit/version to an entity"""
    entity.repo.create()
    in_repo_path = str(entity.repo_abs_path / filename)
    open(in_repo_path, 'w').write('entity contents')
    entity.repo.add_file(in_repo_path)
    commit = entity.repo.commit('file', User(full_name='author', email='author@example.com'))
    if tag_name:
        entity.repo.tag(tag_name)
    return commit


@pytest.mark.django_db
class TestEntityCreation:
    def test_create_model(self, user, client):
        add_permission(user, 'create_model')
        response = client.post('/entities/models/new', data={
            'name': 'mymodel',
            'visibility': 'private',
        })
        assert response.status_code == 302

        assert ModelEntity.objects.count() == 1

        entity = ModelEntity.objects.first()
        assert response.url == '/entities/models/%d/versions/new' % entity.id
        assert entity.name == 'mymodel'
        assert entity.visibility == 'private'
        assert entity.author == user

        assert entity.repo_abs_path.exists()

    def test_create_model_requires_permissions(self, user, client):
        response = client.post(
            '/entities/models/new',
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_create_protocol(self, user, client):
        add_permission(user, 'create_protocol')
        response = client.post('/entities/protocols/new', data={
            'name': 'myprotocol',
            'visibility': 'public',
        })
        assert response.status_code == 302

        assert ProtocolEntity.objects.count() == 1

        entity = ProtocolEntity.objects.first()
        assert response.url == '/entities/protocols/%d/versions/new' % entity.id
        assert entity.name == 'myprotocol'
        assert entity.visibility == 'public'
        assert entity.author == user

        assert entity.repo_abs_path.exists()

    def test_create_protocol_requires_permissions(self, user, client):
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
    def test_owner_can_delete_entity(self, user, client, recipe, url, list_url):
        entity = recipe.make(author=user)
        repo_path = entity.repo_abs_path
        add_version(entity)
        assert Entity.objects.filter(pk=entity.pk).exists()
        assert repo_path.exists()

        response = client.post(url % entity.pk)

        assert response.status_code == 302
        assert response.url == list_url

        assert not Entity.objects.filter(pk=entity.pk).exists()
        assert not repo_path.exists()

    @pytest.mark.usefixtures('user')
    def test_non_owner_cannot_delete_entity(self, other_user, client, recipe, url, list_url):
        entity = recipe.make(author=other_user)
        repo_path = entity.repo_abs_path
        add_version(entity)

        response = client.post(url % entity.pk)

        assert response.status_code == 403
        assert Entity.objects.filter(pk=entity.pk).exists()
        assert repo_path.exists()


@pytest.mark.django_db
class TestEntityDetail:
    def test_redirects_to_latest_version(self, client, user):
        model = recipes.model.make()
        add_version(model)
        response = client.get('/entities/models/%d' % model.pk)
        assert response.status_code == 302
        assert response.url == '/entities/models/%d/versions/latest' % model.pk


@pytest.mark.django_db
class TestEntityVersionDetail:
    def check(self, client, url, version, tags):
        response = client.get(url)
        assert response.status_code == 200
        assert response.context['version'] == version
        assert len(response.context['tags']) == len(tags)
        for actual, expected in zip(response.context['tags'], tags):
            assert actual.name == expected

    def test_view_entity_version(self, client, user):
        model = recipes.model.make()
        add_version(model)
        commit = model.repo.latest_commit
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, commit.hexsha),
                   commit, [])
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   commit, [])

        # Now add a second version with tag
        assert len(list(model.repo.commits)) == 1
        add_version(model)
        model.repo.tag('my_tag')

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

    def test_version_with_two_tags(self, client, user):
        model = recipes.model.make()
        add_version(model)
        commit = model.repo.latest_commit
        model.repo.tag('tag1')
        model.repo.tag('tag2')
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, commit.hexsha),
                   commit, ['tag1', 'tag2'])
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, 'tag1'),
                   commit, ['tag1', 'tag2'])
        self.check(client, '/entities/models/%d/versions/%s' % (model.pk, 'tag2'),
                   commit, ['tag1', 'tag2'])
        self.check(client, '/entities/models/%d/versions/latest' % model.pk,
                   commit, ['tag1', 'tag2'])


@pytest.mark.django_db
class TestTagging:
    def test_tag_specific_ref(self):
        model = recipes.model.make()
        commit = add_version(model)
        add_version(model)
        model.repo.tag('tag', ref=commit.hexsha)
        tags = model.repo.tag_dict
        assert len(tags) == 1
        assert tags[commit][0].name == 'tag'

    def test_nasty_tag_chars(self):
        import git
        model = recipes.model.make()
        add_version(model)

        with pytest.raises(git.exc.GitCommandError):
            model.repo.tag('tag/')

        model.repo.tag('my/tag')
        assert model.repo.tag_dict[model.repo.latest_commit][0].name == 'my/tag'

        with pytest.raises(git.exc.GitCommandError):
            model.repo.tag('tag with spaces')

    def test_cant_use_same_tag_twice(self):
        import git
        model = recipes.model.make()
        add_version(model)
        model.repo.tag('tag')
        add_version(model)
        with pytest.raises(git.exc.GitCommandError):
            model.repo.tag('tag')

    def test_user_can_add_tag(self, user, client):
        add_permission(user, 'create_model_version')
        model = recipes.model.make(author=user)
        add_version(model)
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
        assert tags[commit][0].name == 'v1'

    @pytest.mark.skip('not yet implemented')
    def test_tag_view_requires_permissions(self, user, client):
        model = recipes.model.make(author=user)
        commit = add_version(model)
        response = client.post(
            '/entities/tag/%d/%s' % (model.pk, commit.hexsha),
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url


@pytest.mark.django_db
class TestEntityVersionList:
    def test_view_entity_version_list(self, client, user):
        model = recipes.model.make()
        add_version(model)

        response = client.get('/entities/models/%d/versions/' % model.pk)
        assert response.status_code == 200
        assert response.context['versions'] == [(None, model.repo.latest_commit)]


@pytest.mark.django_db
class TestEntityList:
    def test_lists_my_models(self, client, user):
        models = recipes.model.make(_quantity=2, author=user)
        response = client.get('/entities/models/')
        assert response.status_code == 200
        assert list(response.context['object_list']) == models

    def test_lists_my_protocols(self, client, user):
        protocols = recipes.protocol.make(_quantity=2, author=user)
        response = client.get('/entities/protocols/')
        assert response.status_code == 200
        assert list(response.context['object_list']) == protocols


@pytest.mark.django_db
class TestVersionCreation:
    def test_new_version_form_includes_latest_version(self, client, user):
        model = recipes.model.make()
        commit = add_version(model)
        add_permission(user, 'create_model_version')
        response = client.get('/entities/models/%d/versions/new' % model.pk)
        assert response.status_code == 200
        assert response.context['latest_version'] == commit

    def test_no_latest_version(self, client, user):
        add_permission(user, 'create_model_version')
        model = recipes.model.make()
        response = client.get('/entities/models/%d/versions/new' % model.pk)
        assert response.status_code == 200
        assert 'latest_version' not in response.context

    def test_create_model_version(self, user, client):
        add_permission(user, 'create_model_version')
        model = recipes.model_file.make(
            entity__author=user,
            upload=SimpleUploadedFile('model.txt', b'my test model'),
            original_name='model.txt',
        ).entity
        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'filename[]': 'uploads/model.txt',
                'commit_message': 'first commit',
                'tag': 'v1',
            },
        )
        assert response.status_code == 302
        assert response.url == '/entities/models/%d' % model.id
        assert 'v1' in model.repo._repo.tags
        assert model.repo.latest_commit.message == 'first commit'
        assert 'model.txt' in model.repo.filenames()
        assert 'manifest.xml' in model.repo.filenames()
        assert model.repo.master_filename() is None

    def test_add_multiple_files(self, user, client):
        add_permission(user, 'create_model_version')
        model = recipes.model.make(author=user)
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
            },
        )
        assert response.status_code == 302
        assert response.url == '/entities/models/%d' % model.id
        assert 'v1' in model.repo._repo.tags
        assert model.repo.latest_commit.message == 'files'
        assert 'file1.txt' in model.repo.filenames()
        assert 'file2.txt' in model.repo.filenames()
        assert model.repo.master_filename() == 'file1.txt'

    def test_delete_file(self, user, client):
        add_permission(user, 'create_model_version')
        model = recipes.model.make(author=user)
        add_version(model, 'file1.txt')
        add_version(model, 'file2.txt')
        assert len(model.repo.latest_commit.tree.blobs) == 2

        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'delete_filename[]': ['file1.txt'],
                'commit_message': 'delete file1',
                'tag': 'delete-file',
            },
        )
        assert response.status_code == 302
        assert response.url == '/entities/models/%d' % model.id
        assert 'delete-file' in model.repo._repo.tags
        assert model.repo.latest_commit.message == 'delete file1'
        assert len(model.repo.latest_commit.tree.blobs) == 2
        assert 'file2.txt' in model.repo.filenames()
        assert not (model.repo_abs_path / 'file1.txt').exists()

    def test_delete_multiple_files(self, user, client):
        add_permission(user, 'create_model_version')
        model = recipes.model.make(author=user)
        add_version(model, 'file1.txt')
        add_version(model, 'file2.txt')
        add_version(model, 'file3.txt')
        assert len(model.repo.latest_commit.tree.blobs) == 3

        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'delete_filename[]': ['file1.txt', 'file2.txt'],
                'commit_message': 'delete files',
                'tag': 'delete-files',
            },
        )
        assert response.status_code == 302
        assert response.url == '/entities/models/%d' % model.id
        assert 'delete-files' in model.repo._repo.tags
        assert model.repo.latest_commit.message == 'delete files'
        assert len(model.repo.latest_commit.tree.blobs) == 2
        assert 'file3.txt' in model.repo.filenames()
        assert not (model.repo_abs_path / 'file1.txt').exists()
        assert not (model.repo_abs_path / 'file2.txt').exists()

    def test_delete_nonexistent_file(self, user, client):
        add_permission(user, 'create_model_version')
        model = recipes.model.make(author=user)
        add_version(model, 'file1.txt')

        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={
                'delete_filename[]': ['file2.txt'],
                'commit_message': 'delete file2',
                'version': 'delete-file',
            },
        )
        assert response.status_code == 200
        assert 'delete-file' not in model.repo._repo.tags
        assert model.repo.latest_commit.message != 'delete file2'

    def test_create_model_version_requires_permissions(self, user, client):
        model = recipes.model.make(author=user)
        response = client.post(
            '/entities/models/%d/versions/new' % model.pk,
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_create_protocol_version(self, user, client):
        add_permission(user, 'create_protocol_version')
        protocol = recipes.protocol_file.make(
            entity__author=user,
            upload=SimpleUploadedFile('protocol.txt', b'my test protocol'),
            original_name='protocol.txt',
        ).entity
        response = client.post(
            '/entities/protocols/%d/versions/new' % protocol.pk,
            data={
                'filename[]': 'uploads/protocol.txt',
                'commit_message': 'first commit',
                'tag': 'v1',
            },
        )
        assert response.status_code == 302
        assert response.url == '/entities/protocols/%d' % protocol.id
        assert 'v1' in protocol.repo._repo.tags
        assert protocol.repo.latest_commit.message == 'first commit'
        assert 'protocol.txt' in protocol.repo.filenames()
        assert protocol.repo.latest_commit.author.email == user.email
        assert protocol.repo.latest_commit.author.name == user.full_name

    def test_create_protocol_version_requires_permissions(self, user, client):
        protocol = recipes.protocol.make(author=user)
        response = client.post(
            '/entities/protocols/%d/versions/new' % protocol.pk,
            data={},
        )
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_rolls_back_if_tag_exists(self, user, client):
        add_permission(user, 'create_model_version')
        model = recipes.model.make(author=user)
        first_commit = add_version(model, tag_name='v1')

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
            },
        )
        assert response.status_code == 200
        assert model.repo.latest_commit == first_commit
        assert not (model.repo_abs_path / 'model.txt').exists()


@pytest.mark.django_db
class TestEntityArchive:
    def test_download_archive(self, client):
        model = recipes.model.make()
        commit = add_version(model, filename='file1.txt')

        response = client.get('/entities/models/%d/versions/latest/archive' % model.pk)
        assert response.status_code == 200
        archive = zipfile.ZipFile(BytesIO(response.content))
        assert archive.filelist[0].filename == 'file1.txt'
        assert response['Content-Disposition'] == (
            'attachment; filename=%s_%s.zip' % (model.name, commit.hexsha)
        )

    def test_returns_404_if_no_commits_yet(self, user, client):
        model = recipes.model.make()

        response = client.get('/entities/models/%d/versions/latest/archive' % model.pk)
        assert response.status_code == 404


@pytest.mark.django_db
class TestFileUpload:
    def test_upload_file(self, user, client):
        model = recipes.model.make(author=user)

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

    def test_bad_upload(self, user, client):
        model = recipes.model.make(author=user)

        response = client.post('/entities/%d/upload-file' % model.pk, {})

        assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("recipe,url", [
    (recipes.model, '/entities/models/%d'),
    (recipes.model, '/entities/models/%d/versions/'),
    (recipes.model, '/entities/models/%d/versions/latest'),
    (recipes.model, '/entities/models/%d/versions/latest/archive'),
    (recipes.protocol, '/entities/protocols/%d'),
    (recipes.protocol, '/entities/protocols/%d/versions/'),
    (recipes.protocol, '/entities/protocols/%d/versions/latest'),
    (recipes.protocol, '/entities/protocols/%d/versions/latest/archive'),
])
class TestEntityVisibility:
    def test_private_entity_visible_to_self(self, client, user, recipe, url):
        entity = recipe.make(visibility='private', author=user)
        add_version(entity)
        assert client.get(url % entity.pk, follow=True).status_code == 200

    def test_private_entity_invisible_to_other_user(self, client, user, other_user, recipe, url):
        entity = recipe.make(visibility='private', author=other_user)
        add_version(entity)
        response = client.get(url % entity.pk)
        assert response.status_code == 404

    def test_private_entity_requires_login_for_anonymous(self, client, recipe, url):
        entity = recipe.make(visibility='private')
        add_version(entity)
        response = client.get(url % entity.pk)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_restricted_entity_visible_to_other_user(self, client, user, other_user, recipe, url):
        entity = recipe.make(visibility='restricted', author=other_user)
        add_version(entity)
        assert client.get(url % entity.pk, follow=True).status_code == 200

    def test_restricted_entity_requires_login_for_anonymous(self, client, recipe, url):
        entity = recipe.make(visibility='restricted')
        add_version(entity)
        response = client.get(url % entity.pk)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_public_entity_visible_to_anonymous(self, client, recipe, url):
        entity = recipe.make(visibility='public')
        add_version(entity)
        assert client.get(url % entity.pk, follow=True).status_code == 200

    def test_nonexistent_entity_redirects_anonymous_to_login(self, client, recipe, url):
        response = client.get(url % 10000)
        assert response.status_code == 302
        assert '/login' in response.url

    def test_nonexistent_entity_generates_404_for_user(self, client, user, recipe, url):
        response = client.get(url % 10000)
        assert response.status_code == 404


@pytest.mark.django_db
class TestExperimentMatrix:
    def test_matrix(self, client, user):
        model = recipes.model.make()
        protocol = recipes.protocol.make()
        exp = recipes.experiment.make(model=model, protocol=protocol)

        response = client.get('/entities/experiments/matrix')
        data = json.loads(response.content.decode())
        assert 'getMatrix' in data

        assert str(model.pk) in data['getMatrix']['models']
        assert str(protocol.pk) in data['getMatrix']['protocols']
        assert str(exp.pk) in data['getMatrix']['experiments']
