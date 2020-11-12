import pytest
from unittest.mock import patch, PropertyMock

from core import recipes

from datasets.forms import DatasetColumnMappingForm
from datasets.models import Dataset
from repocache.models import ProtocolIoputs


@pytest.mark.django_db
class TestDatasetColumnMappingForm:
    def test_protocol_ioput_must_match_version(self, mock_column_names, helpers, user):
        protocol = recipes.protocol.make()
        proto_v1 = helpers.add_fake_version(protocol, visibility='public')
        proto_v2 = helpers.add_fake_version(protocol, visibility='public')

        v1_in = recipes.protocol_input.make(protocol_version=proto_v1)
        v2_in = recipes.protocol_input.make(protocol_version=proto_v2)
        ioputs = proto_v1.ioputs

        dataset = recipes.dataset.make(visibility='public', protocol=protocol)
        form = DatasetColumnMappingForm(
            {
                'dataset': dataset.pk,
                'column_name': 'col',
                'column_units': 'meters',
                'protocol_version': proto_v1.pk,
                'protocol_ioput': v1_in.pk,
            },
            dataset=dataset,
            protocol_ioputs=proto_v1.ioputs,
        )
        assert form.is_valid()

        form = DatasetColumnMappingForm(
            {
                'dataset': dataset.pk,
                'column_name': 'col',
                'column_units': 'meters',
                'protocol_version': proto_v1.pk,
                'protocol_ioput': v2_in.pk,
            },
            dataset=dataset,
            protocol_ioputs=proto_v1.ioputs,
        )
        assert not form.is_valid()
        assert 'protocol_ioput' in form.errors

    def test_protocol_version_matches_dataset_protocol(self, mock_column_names, helpers, user):
        proto1, proto2 = recipes.protocol.make(_quantity=2)
        proto1_v1 = helpers.add_fake_version(proto1, visibility='public')
        proto2_v1 = helpers.add_fake_version(proto2, visibility='public')
        proto1_v1_in = recipes.protocol_input.make(protocol_version=proto1_v1)

        dataset = recipes.dataset.make(visibility='public', protocol=proto2)
        form = DatasetColumnMappingForm({
            'dataset': dataset.pk,
            'column_name': 'col',
            'column_units': 'meters',
            'protocol_version': proto1_v1.pk,
            'protocol_ioput': proto1_v1_in.pk,
        }, dataset=dataset, protocol_ioputs=proto1_v1.ioputs)

        assert not form.is_valid()
        assert 'protocol_version' in form.errors

    def test_column_name_is_valid_for_dataset(self, user, public_protocol, mock_column_names):
        proto_v1 = public_protocol.repocache.latest_version
        proto_v1_in = recipes.protocol_input.make(protocol_version=proto_v1)

        dataset = recipes.dataset.make(visibility='public', protocol=public_protocol)
        form = DatasetColumnMappingForm({
            'dataset': dataset.pk,
            'column_name': 'col1',
            'column_units': 'meters',
            'protocol_version': proto_v1.pk,
            'protocol_ioput': proto_v1_in.pk,
        }, dataset=dataset, protocol_ioputs=proto_v1.ioputs)
        assert not form.is_valid()
        assert 'column_name' in form.errors

    def test_column_units_must_be_valid_pint(self, user, public_protocol, mock_column_names):
        proto_v1 = public_protocol.repocache.latest_version
        proto_v1_in = recipes.protocol_input.make(protocol_version=proto_v1)

        dataset = recipes.dataset.make(visibility='public', protocol=public_protocol)
        form = DatasetColumnMappingForm({
            'dataset': dataset.pk,
            'column_name': 'col',
            'column_units': 'unknown',
            'protocol_version': proto_v1.pk,
            'protocol_ioput': proto_v1_in.pk,
        }, dataset=dataset, protocol_ioputs=proto_v1.ioputs)
        assert not form.is_valid()
        assert 'column_units' in form.errors
