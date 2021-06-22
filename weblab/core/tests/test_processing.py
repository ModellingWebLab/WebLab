import pytest

from core.processing import prepend_callback_base


@pytest.mark.django_db
def test_prepend_callback_base(settings):
    settings.CALLBACK_BASE_URL = 'http://test.com/'
    settings.FORCE_SCRIPT_NAME = None

    assert prepend_callback_base('/bla') == 'http://test.com/bla'

    settings.FORCE_SCRIPT_NAME = '/bla'
    assert prepend_callback_base('/bla') == 'http://test.com/'
    assert prepend_callback_base('/bla/bla/morebla') == 'http://test.com/bla/morebla'
    assert prepend_callback_base('/experiments/bla/morebla') == 'http://test.com/experiments/bla/morebla'
