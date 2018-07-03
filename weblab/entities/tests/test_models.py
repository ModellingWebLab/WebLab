import pytest
from django.db.utils import IntegrityError

from core import recipes
from entities.models import ModelEntity, ProtocolEntity


@pytest.mark.django_db
class TestEntityNameUniqueness:
    def test_user_cannot_have_same_named_model(self, user):
        recipes.model.make(author=user, name='mymodel')

        with pytest.raises(IntegrityError):
            ModelEntity.objects.create(author=user, name='mymodel')

    def test_user_can_have_same_named_model_and_protocol(self, user):
        ModelEntity.objects.create(author=user, name='myentity')
        ProtocolEntity.objects.create(author=user, name='myentity')

    def test_different_users_can_have_same_named_model(self):
        user, other_user = recipes.user.make(_quantity=2)
        ModelEntity.objects.create(author=user, name='mymodel')
        assert ModelEntity.objects.create(author=other_user, name='mymodel')


@pytest.mark.django_db
def test_deletion():
    user, other_user = recipes.user.make(_quantity=2)
    model = recipes.model.make(author=user)
    superuser = recipes.user.make(is_superuser=True)

    assert model.is_deletable_by(user)
    assert model.is_deletable_by(superuser)
    assert not model.is_deletable_by(other_user)


@pytest.mark.django_db
class TestEntity:
    def test_str(self):
        model = recipes.model.make(name='test model')
        assert str(model) == 'test model'

    def test_repo_abs_path(self, fake_repo_path):
        model = recipes.model.make()
        path = '%s/%d/models/%d' % (fake_repo_path, model.author.pk, model.pk)

        assert model.repo._root == path
        assert str(model.repo_abs_path) == path

    def test_nice_version(self, model_with_version):
        commit = model_with_version.repo.latest_commit.hexsha
        assert model_with_version.nice_version(commit) == '%s...' % commit[:8]

        model_with_version.repo.tag('v1')
        assert model_with_version.nice_version(commit) == 'v1'
