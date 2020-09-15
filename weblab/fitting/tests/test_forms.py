import pytest

from core import recipes
from fitting.forms import FittingResultCreateForm


@pytest.mark.django_db
class TestFittingResultCreateForm:
    def test_fields(self):
        form = FittingResultCreateForm()
        assert 'model' in form.fields
        assert 'model_version' in form.fields
        assert 'protocol' in form.fields
        assert 'protocol_version' in form.fields
        assert 'fittingspec' in form.fields
        assert 'fittingspec_version' in form.fields
        assert 'dataset' in form.fields

    def test_valid_form(
        self, model_with_version, protocol_with_version,
        fittingspec_with_version, public_dataset, helpers
    ):
        helpers.link_to_protocol(protocol_with_version, public_dataset, fittingspec_with_version)

        form = FittingResultCreateForm({
            'model': model_with_version.pk,
            'model_version': model_with_version.repocache.latest_version.pk,
            'protocol': protocol_with_version.pk,
            'protocol_version': protocol_with_version.repocache.latest_version.pk,
            'fittingspec': fittingspec_with_version.pk,
            'fittingspec_version': fittingspec_with_version.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        })
        assert form.is_valid()

    def test_model_version_must_belong_to_model(
        self, model_with_version, protocol_with_version,
        fittingspec_with_version, public_dataset, helpers
    ):
        helpers.link_to_protocol(protocol_with_version, public_dataset, fittingspec_with_version)

        invalid_version = recipes.cached_model_version.make()
        form = FittingResultCreateForm({
            'model': model_with_version.pk,
            'model_version': invalid_version.pk,
            'protocol': protocol_with_version.pk,
            'protocol_version': protocol_with_version.repocache.latest_version.pk,
            'fittingspec': fittingspec_with_version.pk,
            'fittingspec_version': fittingspec_with_version.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        })
        assert not form.is_valid()
        assert 'model_version' in form.errors

    def test_protocol_version_must_belong_to_protocol(
        self, model_with_version, protocol_with_version,
        fittingspec_with_version, public_dataset, helpers
    ):
        helpers.link_to_protocol(protocol_with_version, public_dataset, fittingspec_with_version)

        invalid_version = recipes.cached_protocol_version.make()
        form = FittingResultCreateForm({
            'model': model_with_version.pk,
            'model_version': model_with_version.repocache.latest_version.pk,
            'protocol': protocol_with_version.pk,
            'protocol_version': invalid_version.pk,
            'fittingspec': fittingspec_with_version.pk,
            'fittingspec_version': fittingspec_with_version.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        })
        assert not form.is_valid()
        assert 'protocol_version' in form.errors

    def test_fittingspec_version_must_belong_to_fittingspec(
        self, model_with_version, protocol_with_version,
        fittingspec_with_version, public_dataset, helpers
    ):

        helpers.link_to_protocol(protocol_with_version, public_dataset, fittingspec_with_version)

        invalid_version = recipes.cached_fittingspec_version.make()
        form = FittingResultCreateForm({
            'model': model_with_version.pk,
            'model_version': model_with_version.repocache.latest_version.pk,
            'protocol': protocol_with_version.pk,
            'protocol_version': protocol_with_version.repocache.latest_version.pk,
            'fittingspec': fittingspec_with_version.pk,
            'fittingspec_version': invalid_version.pk,
            'dataset': public_dataset.pk,
        })
        assert not form.is_valid()
        assert 'fittingspec_version' in form.errors

    def test_protocol_and_fittingspec_must_be_linked(
        self, model_with_version, protocol_with_version,
        fittingspec_with_version, public_dataset, helpers
    ):
        helpers.link_to_protocol(protocol_with_version, public_dataset)

        form = FittingResultCreateForm({
            'model': model_with_version.pk,
            'model_version': model_with_version.repocache.latest_version.pk,
            'protocol': protocol_with_version.pk,
            'protocol_version': protocol_with_version.repocache.latest_version.pk,
            'fittingspec': fittingspec_with_version.pk,
            'fittingspec_version': fittingspec_with_version.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        })
        assert not form.is_valid()
        assert 'protocol' in form.errors

    def test_protocol_and_dataset_must_be_linked(
        self, model_with_version, protocol_with_version,
        fittingspec_with_version, public_dataset, helpers
    ):

        helpers.link_to_protocol(protocol_with_version, fittingspec_with_version)

        form = FittingResultCreateForm({
            'model': model_with_version.pk,
            'model_version': model_with_version.repocache.latest_version.pk,
            'protocol': protocol_with_version.pk,
            'protocol_version': protocol_with_version.repocache.latest_version.pk,
            'fittingspec': fittingspec_with_version.pk,
            'fittingspec_version': fittingspec_with_version.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        })
        assert not form.is_valid()
        assert 'protocol' in form.errors
