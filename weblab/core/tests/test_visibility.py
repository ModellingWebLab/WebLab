import pytest

from core import recipes
from core.visibility import Visibility, get_joint_visibility, visibility_check, visible_entity_ids


def test_get_joint_visibility():
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.PUBLIC) == Visibility.PRIVATE
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.PRIVATE) == Visibility.PRIVATE
    assert get_joint_visibility(Visibility.PUBLIC, Visibility.PUBLIC) == Visibility.PUBLIC


@pytest.mark.django_db
def test_visibility_check(helpers, user, other_user, anon_user):
    my_public, my_private = recipes.model.make(author=user, _quantity=2)
    helpers.add_version(my_public, visibility='public')
    helpers.add_version(my_private, visibility='private')

    other_public, other_private = recipes.model.make(author=other_user, _quantity=2)
    helpers.add_version(other_public, visibility='public')
    helpers.add_version(other_private, visibility='private')

    assert visibility_check(user, my_public)
    assert visibility_check(user, my_private)

    assert visibility_check(user, other_public)
    assert not visibility_check(user, other_private)

    assert visibility_check(anon_user, my_public)
    assert not visibility_check(anon_user, my_private)


@pytest.mark.django_db
def test_visible_entity_ids(helpers, user, other_user, anon_user):
   public = recipes.model.make()
   helpers.add_version(public, visibility = 'public')
   my_private = recipes.protocol.make(author=user)
   helpers.add_version(my_private, visibility = 'private')
   other_private = recipes.protocol.make(author=other_user)
   helpers.add_version(other_private, visibility = 'private')

   assert visible_entity_ids(user) == {public.pk, my_private.pk}
   assert visible_entity_ids(other_user) == {public.pk, other_private.pk}
   assert visible_entity_ids(anon_user) == {public.pk}
