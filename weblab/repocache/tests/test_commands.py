from unittest.mock import call, patch

import pytest

from core import recipes
from repocache.management.commands.populate_entity_cache import Command as PopulateCommand


@pytest.mark.django_db
@patch('repocache.management.commands.populate_entity_cache.populate_entity_cache')
def test_populate_all_entities(mock_populate):
    m1, m2 = recipes.model.make(_quantity=2)
    p1, p2 = recipes.protocol.make(_quantity=2)

    PopulateCommand().handle()

    assert mock_populate.call_count == 4
    mock_populate.assert_has_calls(
        [call(m1), call(m2), call(p1), call(p2)],
        any_order=True
    )

    mock_populate.reset_mock()

    PopulateCommand().handle(entity_id=[m1.pk, p1.pk])

    assert mock_populate.call_count == 2
    mock_populate.assert_has_calls([call(m1), call(p1)], any_order=True)
