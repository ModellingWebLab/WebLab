import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.utils import IntegrityError

from core import recipes
from datasets.models import Dataset


@pytest.fixture
def dataset_creator(logged_in_user, helpers, client, public_protocol):
    def _creator(files, main_file=None):
        dataset = recipes.dataset.make(author=logged_in_user, name='mydataset', protocol=public_protocol)
        helpers.add_permission(logged_in_user, 'create_dataset', Dataset)

        uploads = []
        for (file_name, file_contents) in files:
            recipes.dataset_file.make(
                dataset=dataset,
                upload=SimpleUploadedFile(file_name, file_contents),
                original_name=file_name,
            )
            uploads.append(file_name)

        client.post(
            '/datasets/%d/addfiles' % dataset.pk,
            data={
                'filename[]': ['uploads/' + f for f in uploads],
                'delete_filename[]': [],
                'mainEntry': [main_file] if main_file else [],
            },
        )
        return dataset

    return _creator


@pytest.mark.django_db
class TestDataset:
    def test_str(self):
        dataset = recipes.dataset.make(name='test dataset')
        assert str(dataset) == 'test dataset'

    def test_related_protocol(self, user):
        protocol = recipes.protocol.make(author=user)
        dataset = recipes.dataset.make(author=user, name='mydataset', protocol=protocol)
        assert dataset.protocol == protocol

    @pytest.mark.django_db
    def test_visibility_and_sharing(self, logged_in_user, other_user, anon_user, helpers):
        protocol = recipes.protocol.make()
        recipes.dataset.make(author=logged_in_user, name='mydataset', visibility='public', protocol=protocol)
        assert Dataset.objects.visible_to_user(logged_in_user).count() == 1
        assert Dataset.objects.visible_to_user(anon_user).count() == 1
        recipes.dataset.make(author=logged_in_user, name='mydataset2', visibility='private', protocol=protocol)
        assert Dataset.objects.visible_to_user(logged_in_user).count() == 2
        assert Dataset.objects.visible_to_user(anon_user).count() == 1
        recipes.dataset.make(author=other_user, name='mydataset3', visibility='public', protocol=protocol)
        assert Dataset.objects.visible_to_user(logged_in_user).count() == 3
        assert Dataset.objects.visible_to_user(anon_user).count() == 2
        recipes.dataset.make(author=other_user, name='mydataset4', visibility='moderated', protocol=protocol)
        assert Dataset.objects.visible_to_user(logged_in_user).count() == 4
        assert Dataset.objects.visible_to_user(anon_user).count() == 3
        recipes.dataset.make(author=other_user, name='mydataset5', visibility='private', protocol=protocol)
        assert Dataset.objects.visible_to_user(logged_in_user).count() == 4
        assert Dataset.objects.visible_to_user(anon_user).count() == 3

        shared_dataset = recipes.dataset.make(
            author=logged_in_user, name='mydataset6', visibility='private', protocol=protocol)
        shared_dataset.add_collaborator(other_user)

        assert shared_dataset.collaborators == [other_user]
        assert list(Dataset.objects.shared_with_user(other_user).all()) == [shared_dataset]
        helpers.add_permission(other_user, 'create_dataset', Dataset)
        assert shared_dataset.is_editable_by(other_user)

    def test_column_names_comma_separated(self, dataset_creator):
        dataset = dataset_creator([('data1.csv', b'col1,col2')])
        assert dataset.column_names == ['col1', 'col2']

    def test_column_names_tab_separated(self, dataset_creator):
        dataset = dataset_creator([('data1.csv', b'col1\tcol2')])
        assert dataset.column_names == ['col1', 'col2']

    def test_column_names_from_main_file(self, dataset_creator):
        dataset = dataset_creator(
            [
                ('data1.csv', b'col1\tcol2'),
                ('data2.csv', b'col3\tcol4'),
            ],
            main_file='data2.csv'
        )
        assert dataset.column_names == ['col3', 'col4']

    def test_column_names_empty_if_no_files(self, dataset_creator):
        dataset = dataset_creator([])
        assert dataset.column_names == []

    def test_is_editable_by(self, helpers, public_dataset, user, anon_user):
        helpers.add_permission(public_dataset.author, 'create_dataset', public_dataset)
        assert public_dataset.is_editable_by(public_dataset.author)
        assert not public_dataset.is_editable_by(user)
        assert not public_dataset.is_editable_by(anon_user)


@pytest.mark.django_db
class TestDatasetNameUniqueness:
    def test_user_cannot_have_same_named_dataset(self, user):
        recipes.dataset.make(author=user, name='mydataset')

        with pytest.raises(IntegrityError):
            Dataset.objects.create(author=user, name='mydataset')

    def test_different_users_can_have_same_named_model(self, user, other_user):
        recipes.dataset.make(author=user, name='mydataset')
        other_dataset = recipes.dataset.make(author=other_user, name='mydataset')
        assert other_dataset
