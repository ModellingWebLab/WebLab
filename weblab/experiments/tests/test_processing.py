import pytest

from accounts.models import User
from core import recipes
from experiments.processing import submit_experiment


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
class TestSubmitExperiment:
    def test_creates_new_experiment(self):
        model = recipes.model.make()
        model_version = add_version(model)
        protocol = recipes.protocol.make()
        protocol_version = add_version(protocol)
        user = recipes.user.make()

        version = submit_experiment(model, protocol, user)

        assert version.experiment.model == model
        assert version.experiment.protocol == protocol
        assert version.author == user
        assert version.model_version == model_version.hexsha
        assert version.protocol_version == protocol_version.hexsha
        assert version.experiment.author == user

    def test_uses_existing_experiment(self):
        model = recipes.model.make()
        add_version(model)
        protocol = recipes.protocol.make()
        add_version(protocol)
        user = recipes.user.make()
        experiment = recipes.experiment.make(model=model, protocol=protocol)

        version = submit_experiment(model, protocol, user)

        assert version.experiment == experiment
