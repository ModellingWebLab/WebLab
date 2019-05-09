import pytest

from core import recipes
from core.visibility import (
    Visibility,
    get_joint_visibility,
    visibility_check,
    visible_entity_ids
)
from accounts.models import User


def test_get_joint_visibility():
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.PUBLIC) == Visibility.PRIVATE
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.PRIVATE) == Visibility.PRIVATE
    assert get_joint_visibility(Visibility.PUBLIC, Visibility.PUBLIC) == Visibility.PUBLIC
    assert get_joint_visibility(Visibility.PUBLIC, Visibility.MODERATED) == Visibility.PUBLIC
    assert get_joint_visibility(Visibility.MODERATED, Visibility.MODERATED) == Visibility.MODERATED


@pytest.mark.django_db
def test_visibility_check(user, other_user, anon_user):
    assert visibility_check('moderated', [user], user)
    assert visibility_check('public', [user], user)
    assert visibility_check('private', [user], user)

    assert visibility_check('moderated', [], other_user)
    assert visibility_check('public', [], other_user)
    assert not visibility_check('private', [], other_user)

    assert visibility_check('moderated', [], anon_user)
    assert visibility_check('public', [], anon_user)
    assert not visibility_check('private', [], anon_user)


@pytest.mark.django_db
def test_visible_entity_ids(helpers, user, other_user, anon_user):
    public = recipes.model.make()
    helpers.add_version(public, visibility='public')
    moderated = recipes.model.make()
    helpers.add_version(moderated, visibility='moderated')
    my_private = recipes.protocol.make(author=user)
    helpers.add_version(my_private, visibility='private')
    other_private = recipes.protocol.make(author=other_user)
    helpers.add_version(other_private, visibility='private')

    assert visible_entity_ids(user) == {moderated.pk, public.pk, my_private.pk}
    assert visible_entity_ids(other_user) == {moderated.pk, public.pk, other_private.pk}
    assert visible_entity_ids(anon_user) == {moderated.pk, public.pk}

    other_private.add_collaborator(user)
    assert other_private.pk not in visible_entity_ids(user)

    user = User.objects.get(pk=user.pk)
    helpers.add_permission(user, 'create_model')
    assert other_private.pk in visible_entity_ids(user)
