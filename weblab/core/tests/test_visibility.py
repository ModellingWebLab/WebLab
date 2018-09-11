import pytest

from core import recipes
from core.visibility import Visibility, get_joint_visibility, visibility_check


def test_get_joint_visibility():
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.PUBLIC) == Visibility.PRIVATE
    assert get_joint_visibility(Visibility.RESTRICTED, Visibility.PUBLIC) == Visibility.RESTRICTED
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.RESTRICTED) == Visibility.PRIVATE


@pytest.mark.django_db
def test_visibility_check(helpers, user, other_user, anon_user):
    my_public, my_restricted, my_private = recipes.model.make(author=user, _quantity=3)
    helpers.add_version(my_public, visibility='public')
    helpers.add_version(my_restricted, visibility='restricted')
    helpers.add_version(my_private, visibility='private')

    other_public, other_restricted, other_private = \
        recipes.model.make(author=other_user, _quantity=3)
    helpers.add_version(other_public, visibility='public')
    helpers.add_version(other_restricted, visibility='restricted')
    helpers.add_version(other_private, visibility='private')

    assert visibility_check(user, my_public)
    assert visibility_check(user, my_restricted)
    assert visibility_check(user, my_private)

    assert visibility_check(user, other_public)
    assert visibility_check(user, other_restricted)
    assert not visibility_check(user, other_private)

    assert visibility_check(anon_user, my_public)
    assert not visibility_check(anon_user, my_restricted)
    assert not visibility_check(anon_user, my_private)
