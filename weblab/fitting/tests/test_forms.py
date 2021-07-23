import pytest
from core import recipes
from fitting.forms import FittingResultCreateForm


@pytest.mark.django_db
class TestFittingResultCreateForm:
    def test_fields_exist(self, fits_user):
        form = FittingResultCreateForm(user=fits_user)
        assert 'model' in form.fields
        assert 'model_version' in form.fields
        assert 'protocol' in form.fields
        assert 'protocol_version' in form.fields
        assert 'fittingspec' in form.fields
        assert 'fittingspec_version' in form.fields
        assert 'dataset' in form.fields

    def test_fields_enabled_by_default(self, fits_user):
        form = FittingResultCreateForm(user=fits_user)
        assert not form.fields['model'].disabled
        assert not form.fields['protocol'].disabled
        assert not form.fields['fittingspec'].disabled
        assert not form.fields['dataset'].disabled

    def test_disables_preselected_model(self, public_model, fits_user):
        form = FittingResultCreateForm(initial={'model': public_model.pk}, user=fits_user)
        assert form.fields['model'].disabled

    def test_disables_preselected_protocol(self, public_protocol, fits_user):
        form = FittingResultCreateForm(initial={'protocol': public_protocol.pk}, user=fits_user)
        assert form.fields['protocol'].disabled

    def test_disables_preselected_fittingspec(self, public_fittingspec, fits_user):
        form = FittingResultCreateForm(initial={'fittingspec': public_fittingspec.pk}, user=fits_user)
        assert form.fields['fittingspec'].disabled

    def test_disables_preselected_dataset(self, public_dataset, fits_user):
        form = FittingResultCreateForm(initial={'dataset': public_dataset.pk}, user=fits_user)
        assert form.fields['dataset'].disabled

    def test_valid_form(
        self, public_model, public_protocol,
        public_fittingspec, public_dataset, fits_user, helpers
    ):
        helpers.link_to_protocol(public_protocol, public_dataset, public_fittingspec)

        form = FittingResultCreateForm({
            'model': public_model.pk,
            'model_version': public_model.repocache.latest_version.pk,
            'protocol': public_protocol.pk,
            'protocol_version': public_protocol.repocache.latest_version.pk,
            'fittingspec': public_fittingspec.pk,
            'fittingspec_version': public_fittingspec.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        }, user=fits_user)
        assert form.is_valid()

    def test_model_version_must_be_visible(
        self, private_model, public_protocol,
        public_fittingspec, public_dataset, fits_user, helpers
    ):
        helpers.link_to_protocol(public_protocol, public_dataset, public_fittingspec)

        form = FittingResultCreateForm({
            'model': private_model.pk,
            'model_version': private_model.repocache.latest_version.pk,
            'protocol': public_protocol.pk,
            'protocol_version': public_protocol.repocache.latest_version.pk,
            'fittingspec': public_fittingspec.pk,
            'fittingspec_version': public_fittingspec.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        }, user=fits_user)
        assert not form.is_valid()
        assert 'model_version' in form.errors
        assert form.errors['model_version'][0].startswith("Select a valid choice.")

    def test_protocol_version_must_be_visible(
        self, public_model, private_protocol,
        public_fittingspec, public_dataset, fits_user, helpers
    ):
        helpers.link_to_protocol(private_protocol, public_dataset, public_fittingspec)

        form = FittingResultCreateForm({
            'model': public_model.pk,
            'model_version': public_model.repocache.latest_version.pk,
            'protocol': private_protocol.pk,
            'protocol_version': private_protocol.repocache.latest_version.pk,
            'fittingspec': public_fittingspec.pk,
            'fittingspec_version': public_fittingspec.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        }, user=fits_user)
        assert not form.is_valid()
        assert 'protocol_version' in form.errors
        assert form.errors['protocol_version'][0].startswith("Select a valid choice.")

    def test_fittingspec_version_must_be_visible(
        self, public_model, public_protocol,
        private_fittingspec, public_dataset, fits_user, helpers
    ):
        helpers.link_to_protocol(public_protocol, public_dataset, private_fittingspec)

        form = FittingResultCreateForm({
            'model': public_model.pk,
            'model_version': public_model.repocache.latest_version.pk,
            'protocol': public_protocol.pk,
            'protocol_version': public_protocol.repocache.latest_version.pk,
            'fittingspec': private_fittingspec.pk,
            'fittingspec_version': private_fittingspec.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        }, user=fits_user)
        assert not form.is_valid()
        assert 'fittingspec_version' in form.errors
        assert form.errors['fittingspec_version'][0].startswith("Select a valid choice.")

    def test_dataset_must_be_visible(
        self, public_model, public_protocol, public_fittingspec, private_dataset, fits_user, helpers
    ):
        helpers.link_to_protocol(public_protocol, private_dataset, public_fittingspec)

        form = FittingResultCreateForm({
            'model': public_model.pk,
            'model_version': public_model.repocache.latest_version.pk,
            'protocol': public_protocol.pk,
            'protocol_version': public_protocol.repocache.latest_version.pk,
            'fittingspec': public_fittingspec.pk,
            'fittingspec_version': public_fittingspec.repocache.latest_version.pk,
            'dataset': private_dataset.pk,
        }, user=fits_user)
        assert not form.is_valid()
        assert 'dataset' in form.errors
        assert form.errors['dataset'][0].startswith("Select a valid choice.")

    def test_only_shows_visible_models(self, private_model, public_model, fits_user):
        form = FittingResultCreateForm(user=fits_user)
        assert form.fields['model'].valid_value(public_model.pk)
        assert not form.fields['model'].valid_value(private_model.pk)

    def test_only_shows_visible_protocols(self, private_protocol, public_protocol, fits_user):
        form = FittingResultCreateForm(user=fits_user)
        assert form.fields['protocol'].valid_value(public_protocol.pk)
        assert not form.fields['protocol'].valid_value(private_protocol.pk)

    def test_only_shows_visible_fittingspecs(self, private_fittingspec, public_fittingspec, fits_user):
        form = FittingResultCreateForm(user=fits_user)
        assert form.fields['fittingspec'].valid_value(public_fittingspec.pk)
        assert not form.fields['fittingspec'].valid_value(private_fittingspec.pk)

    def test_only_shows_visible_datasets(self, private_dataset, public_dataset, fits_user):
        form = FittingResultCreateForm(user=fits_user)
        assert form.fields['dataset'].valid_value(public_dataset.pk)
        assert not form.fields['dataset'].valid_value(private_dataset.pk)

    def test_model_version_must_belong_to_model(
        self, public_model, public_protocol,
        public_fittingspec, public_dataset, fits_user, helpers
    ):
        helpers.link_to_protocol(public_protocol, public_dataset, public_fittingspec)

        invalid_version = recipes.cached_model_version.make()
        form = FittingResultCreateForm({
            'model': public_model.pk,
            'model_version': invalid_version.pk,
            'protocol': public_protocol.pk,
            'protocol_version': public_protocol.repocache.latest_version.pk,
            'fittingspec': public_fittingspec.pk,
            'fittingspec_version': public_fittingspec.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        }, user=fits_user)
        assert not form.is_valid()
        assert 'model_version' in form.errors

    def test_protocol_version_must_belong_to_protocol(
        self, public_model, public_protocol,
        public_fittingspec, public_dataset, fits_user, helpers
    ):
        helpers.link_to_protocol(public_protocol, public_dataset, public_fittingspec)

        invalid_version = recipes.cached_protocol_version.make()
        form = FittingResultCreateForm({
            'model': public_model.pk,
            'model_version': public_model.repocache.latest_version.pk,
            'protocol': public_protocol.pk,
            'protocol_version': invalid_version.pk,
            'fittingspec': public_fittingspec.pk,
            'fittingspec_version': public_fittingspec.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        }, user=fits_user)
        assert not form.is_valid()
        assert 'protocol_version' in form.errors

    def test_fittingspec_version_must_belong_to_fittingspec(
        self, public_model, public_protocol,
        public_fittingspec, public_dataset, fits_user, helpers
    ):

        helpers.link_to_protocol(public_protocol, public_dataset, public_fittingspec)

        invalid_version = recipes.cached_fittingspec_version.make()
        form = FittingResultCreateForm({
            'model': public_model.pk,
            'model_version': public_model.repocache.latest_version.pk,
            'protocol': public_protocol.pk,
            'protocol_version': public_protocol.repocache.latest_version.pk,
            'fittingspec': public_fittingspec.pk,
            'fittingspec_version': invalid_version.pk,
            'dataset': public_dataset.pk,
        }, user=fits_user)
        assert not form.is_valid()
        assert 'fittingspec_version' in form.errors

    def test_protocol_and_fittingspec_must_be_linked(
        self, public_model, public_protocol,
        public_fittingspec, public_dataset, fits_user, helpers
    ):
        helpers.link_to_protocol(public_protocol, public_dataset)

        form = FittingResultCreateForm({
            'model': public_model.pk,
            'model_version': public_model.repocache.latest_version.pk,
            'protocol': public_protocol.pk,
            'protocol_version': public_protocol.repocache.latest_version.pk,
            'fittingspec': public_fittingspec.pk,
            'fittingspec_version': public_fittingspec.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        }, user=fits_user)
        assert not form.is_valid()
        assert 'protocol' in form.errors

    def test_protocol_and_dataset_must_be_linked(
        self, public_model, public_protocol,
        public_fittingspec, public_dataset, fits_user, helpers
    ):

        helpers.link_to_protocol(public_protocol, public_fittingspec)

        form = FittingResultCreateForm({
            'model': public_model.pk,
            'model_version': public_model.repocache.latest_version.pk,
            'protocol': public_protocol.pk,
            'protocol_version': public_protocol.repocache.latest_version.pk,
            'fittingspec': public_fittingspec.pk,
            'fittingspec_version': public_fittingspec.repocache.latest_version.pk,
            'dataset': public_dataset.pk,
        }, user=fits_user)
        assert not form.is_valid()
        assert 'protocol' in form.errors
