from core.visibility import Visibility, get_joint_visibility


def test_get_joint_visibility():
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.PUBLIC) == Visibility.PRIVATE
    assert get_joint_visibility(Visibility.RESTRICTED, Visibility.PUBLIC) == Visibility.RESTRICTED
    assert get_joint_visibility(Visibility.PRIVATE, Visibility.RESTRICTED) == Visibility.PRIVATE
