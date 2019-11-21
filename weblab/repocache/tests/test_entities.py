import pytest

from core import recipes
from repocache.entities import get_moderated_entity_ids, get_public_entity_ids


@pytest.mark.django_db
def test_get_public_entity_ids():
    e1, e2 = recipes.cached_model.make(_quantity=2)
    e3, e4 = recipes.cached_protocol.make(_quantity=2)
    e1v1 = recipes.cached_model_version.make(visibility='public', entity=e1)  # noqa: F841
    e1v2 = recipes.cached_model_version.make(visibility='private', entity=e1)  # noqa: F841

    e2v1 = recipes.cached_model_version.make(visibility='private', entity=e2)  # noqa: F841
    e2v2 = recipes.cached_model_version.make(visibility='public', entity=e2)  # noqa: F841

    e3v1 = recipes.cached_protocol_version.make(visibility='private', entity=e3)  # noqa: F841
    e3v2 = recipes.cached_protocol_version.make(visibility='moderated', entity=e3)  # noqa: F841

    e4v1 = recipes.cached_protocol_version.make(visibility='private', entity=e4)  # noqa: F841

    assert get_public_entity_ids() == {e1.entity.id, e2.entity.id, e3.entity.id}
    assert get_moderated_entity_ids() == {e3.entity.id}
