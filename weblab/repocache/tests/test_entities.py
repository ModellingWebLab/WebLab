import pytest

from core import recipes
from repocache.entities import get_public_entity_ids


@pytest.mark.django_db
def test_get_public_entity_ids():
    e1, e2, e3 = recipes.cached_entity.make(_quantity=3)
    e1v1 = recipes.cached_entity_version.make(visibility='public', entity=e1)
    e1v2 = recipes.cached_entity_version.make(visibility='private', entity=e1)

    e2v1 = recipes.cached_entity_version.make(visibility='private', entity=e2)
    e2v2 = recipes.cached_entity_version.make(visibility='public', entity=e2)

    assert get_public_entity_ids() == { e2.entity.id }
