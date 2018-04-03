import pytest

from core import recipes
from experiments.processing import submit_experiment


@pytest.mark.django_db
class TestSubmitExperiment:
    def test_creates_new_experiment(self, helpers):
        model = recipes.model.make()
        model_version = helpers.add_version(model)
        protocol = recipes.protocol.make()
        protocol_version = helpers.add_version(protocol)
        user = recipes.user.make()

        version = submit_experiment(model, protocol, user)

        assert version.experiment.model == model
        assert version.experiment.protocol == protocol
        assert version.author == user
        assert version.model_version == model_version.hexsha
        assert version.protocol_version == protocol_version.hexsha
        assert version.experiment.author == user

    def test_uses_existing_experiment(self, helpers):
        model = recipes.model.make()
        helpers.add_version(model)
        protocol = recipes.protocol.make()
        helpers.add_version(protocol)
        user = recipes.user.make()
        experiment = recipes.experiment.make(model=model, protocol=protocol)

        version = submit_experiment(model, protocol, user)

        assert version.experiment == experiment
