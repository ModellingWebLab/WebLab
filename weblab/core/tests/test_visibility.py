import pytest

from core import recipes
from core.visibility import Visibility, get_joint_visibility, visibility_check


def test_get_joint_visibility():
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.PUBLIC) == Visibility.PRIVATE
    assert get_joint_visibility(Visibility.RESTRICTED, Visibility.PUBLIC) == Visibility.RESTRICTED
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.RESTRICTED) == Visibility.PRIVATE


@pytest.mark.django_db
def test_visibility_check(user, other_user, anon_user):
    my_public = recipes.model.make(author=user, visibility='public')
    my_restricted = recipes.model.make(author=user, visibility='restricted')
    my_private = recipes.model.make(author=user, visibility='private')
    other_public = recipes.model.make(author=other_user, visibility='public')
    other_restricted = recipes.model.make(author=other_user, visibility='restricted')
    other_private = recipes.model.make(author=other_user, visibility='private')

    assert visibility_check(user, my_public)
    assert visibility_check(user, my_restricted)
    assert visibility_check(user, my_private)

    assert visibility_check(user, other_public)
    assert visibility_check(user, other_restricted)
    assert not visibility_check(user, other_private)

    assert visibility_check(anon_user, my_public)
    assert not visibility_check(anon_user, my_restricted)
    assert not visibility_check(anon_user, my_private)
