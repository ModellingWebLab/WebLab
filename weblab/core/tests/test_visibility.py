import pytest

from core.visibility import (
    Visibility,
    get_joint_visibility,
    visibility_check,
    visibility_meets_threshold,
)


def test_get_joint_visibility():
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.PUBLIC) == Visibility.PRIVATE
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.PRIVATE) == Visibility.PRIVATE
    assert get_joint_visibility(Visibility.PUBLIC, Visibility.PUBLIC) == Visibility.PUBLIC
    assert get_joint_visibility(Visibility.PUBLIC, Visibility.MODERATED) == Visibility.PUBLIC
    assert get_joint_visibility(Visibility.MODERATED, Visibility.MODERATED) == Visibility.MODERATED


def test_visibility_threshold():
    assert visibility_meets_threshold(Visibility.PRIVATE, None)
    assert visibility_meets_threshold(Visibility.PUBLIC, None)
    assert visibility_meets_threshold(Visibility.MODERATED, None)
    assert not visibility_meets_threshold(Visibility.PRIVATE, Visibility.PUBLIC)
    assert visibility_meets_threshold(Visibility.PUBLIC, Visibility.PUBLIC)
    assert visibility_meets_threshold(Visibility.MODERATED, Visibility.PUBLIC)
    assert not visibility_meets_threshold(Visibility.PRIVATE, Visibility.MODERATED)
    assert not visibility_meets_threshold(Visibility.PUBLIC, Visibility.MODERATED)
    assert visibility_meets_threshold(Visibility.MODERATED, Visibility.MODERATED)


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
