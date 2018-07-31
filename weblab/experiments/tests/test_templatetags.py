import pytest

import experiments.templatetags.experiments as exp_tags
from core import recipes


@pytest.mark.django_db
def test_url_comparison_json():
    versions = recipes.experiment_version.make(_quantity=3)

    compare_url = '/experiments/compare/%d/%d/%d/info' % tuple(ver.id for ver in versions)
    assert exp_tags.url_comparison_json(versions) == compare_url

    assert exp_tags.url_comparison_json([]) == '/experiments/compare/info'


@pytest.mark.django_db
def test_url_comparison_base():
    assert exp_tags.url_comparison_base() == '/experiments/compare'


@pytest.mark.django_db
def test_url_version_comparison_matrix():
    model = recipes.model.make()
    assert ((exp_tags.url_version_comparison_matrix(model) ==
            '/experiments/models/%d/versions/*' % model.pk))

    proto = recipes.protocol.make()
    assert ((exp_tags.url_version_comparison_matrix(proto) ==
            '/experiments/protocols/%d/versions/*' % proto.pk))
