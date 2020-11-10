import pytest

from core import recipes

from datasets.forms import DatasetColumnMappingForm, DatasetColumnMappingFormSet
from repocache.models import ProtocolIoputs


@pytest.mark.django_db
class TestDatasetColumnMappingFormSet:
    def test_has_formset(self, public_dataset, user):
        formset = DatasetColumnMappingFormSet(instance=public_dataset, user=user)
        assert formset.instance == public_dataset

    def test_has_versions(self, user, helpers):
        protocol = recipes.protocol.make()
        proto_v1 = helpers.add_fake_version(protocol, visibility='public')
        proto_v2 = helpers.add_fake_version(protocol, visibility='private')
        proto_v3 = helpers.add_fake_version(protocol, visibility='public')

        dataset = recipes.dataset.make(visibility='public', protocol=protocol)

        formset = DatasetColumnMappingFormSet(instance=dataset, user=user)
        #response = client.get('/datasets/%d/map' % dataset.pk)

        form0 = formset[0]
        pv_field = form0.fields['protocol_version']
        assert pv_field.valid_value(proto_v1.pk)
        assert not pv_field.valid_value(proto_v2.pk)
        assert pv_field.valid_value(proto_v3.pk)

    def test_has_ioputs(self, user, helpers):
        protocol = recipes.protocol.make()
        proto_v1 = helpers.add_fake_version(protocol, visibility='private')
        proto_v2 = helpers.add_fake_version(protocol, visibility='public')

        # linked to private version
        v1_in = recipes.protocol_input.make(protocol_version=proto_v1)

        # linked to a public version
        v2_in = recipes.protocol_input.make(protocol_version=proto_v2)
        v2_out = recipes.protocol_output.make(protocol_version=proto_v2)
        v2_flag = recipes.protocol_ioput_flag.make(protocol_version=proto_v2)

        # another input, linked to a different protocol and version
        other_in = recipes.protocol_input.make()

        dataset = recipes.dataset.make(visibility='public', protocol=protocol)

        formset = DatasetColumnMappingFormSet(instance=dataset, user=user)

        form0 = formset[0]
        pv_field = form0.fields['protocol_ioput']

        assert not pv_field.valid_value(v1_in.pk)
        assert pv_field.valid_value(v2_in.pk)
        assert pv_field.valid_value(v2_out.pk)
        assert not pv_field.valid_value(v2_flag.pk)
        assert not pv_field.valid_value(other_in.pk)

    def _make_form(self, dataset, user, data):
        versions = dataset.protocol.cachedentity.versions.visible_to_user(user)
        ioputs = ProtocolIoputs.objects.filter(
            protocol_version__in=versions,
            kind__in=(ProtocolIoputs.INPUT, ProtocolIoputs.OUTPUT)
        )
        return DatasetColumnMappingForm(
            data,
            dataset=dataset,
            protocol_versions=versions,
            protocol_ioputs=ioputs,
        )

    def test_protocol_ioput_must_match_version(self, helpers, user):
        protocol = recipes.protocol.make()
        proto_v1 = helpers.add_fake_version(protocol, visibility='public')
        proto_v2 = helpers.add_fake_version(protocol, visibility='public')

        v1_in = recipes.protocol_input.make(protocol_version=proto_v1)
        v2_in = recipes.protocol_input.make(protocol_version=proto_v2)

        dataset = recipes.dataset.make(visibility='public', protocol=protocol)

        form = self._make_form(dataset, user, {
            'column_name': 'col',
            'column_units': 'units',
            'protocol_version': proto_v1.pk,
            'protocol_ioput': v1_in.pk,
        })
        assert form.is_valid()

        form = self._make_form(dataset, user, {
            'column_name': 'col',
            'column_units': 'units',
            'protocol_version': proto_v1.pk,
            'protocol_ioput': v2_in.pk,
        })
        assert not form.is_valid()
        assert 'protocol_ioput' in form.errors

    def test_protocol_version_matches_dataset_protocol(self, helpers, user):
        proto1, proto2 = recipes.protocol.make(_quantity=2)
        proto1_v1 = helpers.add_fake_version(proto1, visibility='public')
        proto2_v1 = helpers.add_fake_version(proto2, visibility='public')
        proto1_v1_in = recipes.protocol_input.make(protocol_version=proto1_v1)

        dataset = recipes.dataset.make(visibility='public', protocol=proto2)

        form = self._make_form(dataset, user, {
            'column_name': 'col',
            'column_units': 'units',
            'protocol_version': proto1_v1.pk,
            'protocol_ioput': proto1_v1_in.pk,
        })
        assert not form.is_valid()
        assert 'protocol_version' in form.errors

    def test_column_units_are_valid_pint(self):
        pass

    def test_no_duplicate_column_mappings(self):
        pass

    def test_valid_column_names_for_dataset(self):
        pass
