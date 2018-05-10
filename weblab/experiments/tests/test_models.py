from datetime import date

import pytest

from core import recipes


@pytest.mark.django_db
class TestExperiment:
    def test_name(self):
        experiment = recipes.experiment.make(
            model__name='my model',
            protocol__name='my protocol'
        )

        assert str(experiment) == experiment.name == 'my model / my protocol'

    def test_latest_version(self):
        v1 = recipes.experiment_version.make(created_at=date(2017, 1, 2))
        v2 = recipes.experiment_version.make(experiment=v1.experiment, created_at=date(2017, 1, 3))

        assert v1.experiment.latest_version == v2

    def test_latest_result(self):
        ver = recipes.experiment_version.make(created_at=date(2017, 1, 2), status='FAILED')

        assert ver.experiment.latest_result == 'FAILED'

    def test_latest_result_empty_if_no_versions(self):
        exp = recipes.experiment.make()

        assert exp.latest_result == ''
