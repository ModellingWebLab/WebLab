import pytest

from django.conf import settings
from urllib.parse import urljoin
from core.processing import prepend_callback_base

@pytest.mark.django_db
def test_prepend_callback_base():
    old_callback_base = settings.CALLBACK_BASE_URL
    old_script_name = settings.FORCE_SCRIPT_NAME
    settings.CALLBACK_BASE_URL = 'http://test.com/'
    settings.FORCE_SCRIPT_NAME = None

    assert prepend_callback_base('/bla') ==  'http://test.com/bla'

    settings.FORCE_SCRIPT_NAME = '/bla'
    assert prepend_callback_base('/bla') ==  'http://test.com/'
    assert prepend_callback_base('/bla/bla/morebla') ==  'http://test.com/bla/morebla'
    assert prepend_callback_base('/experiments/bla/morebla') ==  'http://test.com/experiments/bla/morebla'





    settings.CALLBACK_BASE_URL = old_callback_base
    settings.FORCE_SCRIPT_NAME = old_script_name

