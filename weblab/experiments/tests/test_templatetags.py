import pytest

import experiments.templatetags.experiments as exp_tags
from core import recipes
from django.urls import reverse


@pytest.mark.django_db
def test_url_experiment_comparison_json():
    versions = recipes.experiment_version.make(_quantity=3)

    compare_url = '/experiments/compare/%d/%d/%d/info' % tuple(ver.id for ver in versions)
    assert exp_tags.url_experiment_comparison_json(versions) == compare_url

    assert exp_tags.url_experiment_comparison_json([]) == '/experiments/compare/info'


@pytest.mark.django_db
def test_dataset_options(logged_in_user, client):
    model = recipes.model.make()
    protocol = recipes.protocol.make()
    dataset = recipes.dataset.make(author=logged_in_user, name='mydataset', visibility='public', protocol=protocol)
    experiment = recipes.experiment.make(model=model, protocol=protocol)
    context = {'user': logged_in_user}
    assert (exp_tags.dataset_options(context, experiment) == '<option value="' +
             reverse('datasets:version_json', args=(dataset.id,)) + '">mydataset</option>')


@pytest.mark.django_db
def test_url_experiment_comparison_base():
    assert exp_tags.url_experiment_comparison_base() == '/experiments/compare'


@pytest.mark.django_db
def test_url_version_comparison_matrix():
    model = recipes.model.make()
    assert ((exp_tags.url_version_comparison_matrix(model) ==
            '/experiments/models/%d/versions/*' % model.pk))

    proto = recipes.protocol.make()
    assert ((exp_tags.url_version_comparison_matrix(proto) ==
            '/experiments/protocols/%d/versions/*' % proto.pk))
