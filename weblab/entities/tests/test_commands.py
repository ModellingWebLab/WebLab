from unittest.mock import call, patch

import pytest

from core import recipes
from entities.management.commands.analyse_entity_versions import Command as AnalyseCommand


@pytest.mark.django_db
@patch('entities.models.ProtocolEntity.analyse_new_version', autospec=True)
@patch('entities.models.Entity.analyse_new_version', autospec=True)
def test_analyse_all_entities(mock_base_analyse, mock_proto_analyse, helpers):
    m1, m2 = recipes.model.make(_quantity=2)
    p1, p2 = recipes.protocol.make(_quantity=2)
    c1 = helpers.add_version(m1, filename='c1.txt')
    c2 = helpers.add_version(m2, filename='c2.txt')
    c3 = helpers.add_version(p1, filename='c3.txt')
    c4 = helpers.add_version(p1, filename='c4.txt')
    c5 = helpers.add_version(p2, filename='c5.txt')

    AnalyseCommand().handle()

    assert mock_base_analyse.call_count == 2
    assert mock_proto_analyse.call_count == 3
    mock_base_analyse.assert_has_calls(
        [call(m1, c1), call(m2, c2)],
        any_order=True
    )
    mock_proto_analyse.assert_has_calls(
        [call(p1, c3), call(p1, c4), call(p2, c5)],
        any_order=True
    )

    mock_base_analyse.reset_mock()
    mock_proto_analyse.reset_mock()

    AnalyseCommand().handle(entity_id=[m1.pk, p1.pk])

    assert mock_base_analyse.call_count == 1
    assert mock_proto_analyse.call_count == 2
    mock_base_analyse.assert_has_calls([call(m1, c1)])
    mock_proto_analyse.assert_has_calls([call(p1, c4), call(p1, c3)])
