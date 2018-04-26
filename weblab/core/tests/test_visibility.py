from core.visibility import PRIVATE, PUBLIC, RESTRICTED, get_joint_visibility


def test_get_joint_visibility():
    assert get_joint_visibility(PRIVATE, PUBLIC) == PRIVATE
    assert get_joint_visibility(RESTRICTED, PUBLIC) == RESTRICTED
    assert get_joint_visibility(PRIVATE, RESTRICTED) == PRIVATE
