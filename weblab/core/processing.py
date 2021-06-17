from urllib.parse import urljoin

from django.conf import settings

def prepend_callback_base(url_path):
    """Prepend CALLBACK_BASE_UR to url_path. If we are running in a subfolder this is striped from url_path."""

    if hasattr(settings, 'FORCE_SCRIPT_NAME'):
         url_path = url_path.replace(settings.FORCE_SCRIPT_NAME, '')
    return urljoin(settings.CALLBACK_BASE_URL, url_path)

