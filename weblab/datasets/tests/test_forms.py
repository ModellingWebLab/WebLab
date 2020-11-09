import pytest

from core import recipes

from datasets.forms import DatasetColumnMappingFormSet


@pytest.mark.django_db
class TestDatasetColumnMappingFormSet:
    def test_has_formset(self, public_dataset, logged_in_user):
        formset = DatasetColumnMappingFormSet(instance=public_dataset, user=logged_in_user)
        assert formset.instance == public_dataset

    def test_has_versions(self, client, logged_in_user, helpers):
        protocol = recipes.protocol.make()
        proto_v1 = helpers.add_fake_version(protocol, visibility='public')
        proto_v2 = helpers.add_fake_version(protocol, visibility='private')
        proto_v3 = helpers.add_fake_version(protocol, visibility='public')

        dataset = recipes.dataset.make(visibility='public', protocol=protocol)

        formset = DatasetColumnMappingFormSet(instance=dataset, user=logged_in_user)
        #response = client.get('/datasets/%d/map' % dataset.pk)

        form0 = formset[0]
        pv_field = form0.fields['protocol_version']
        assert pv_field.valid_value(proto_v1.pk)
        assert not pv_field.valid_value(proto_v2.pk)
        assert pv_field.valid_value(proto_v3.pk)

    def test_has_ioputs(self, client, logged_in_user, helpers):
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

        formset = DatasetColumnMappingFormSet(instance=dataset, user=logged_in_user)

        form0 = formset[0]
        pv_field = form0.fields['protocol_ioput']

        assert not pv_field.valid_value(v1_in.pk)
        assert pv_field.valid_value(v2_in.pk)
        assert pv_field.valid_value(v2_out.pk)
        assert not pv_field.valid_value(v2_flag.pk)
        assert not pv_field.valid_value(other_in.pk)
