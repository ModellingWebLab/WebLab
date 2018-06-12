import pytest

from core import recipes
from experiments.templatetags.experiments import url_comparison_json


@pytest.mark.django_db
def test_url_comparison_json():
    versions = recipes.experiment_version.make(_quantity=3)

    compare_url = '/experiments/compare/%d/%d/%d/info' % tuple(ver.id for ver in versions)
    assert url_comparison_json(versions) == compare_url
