from urllib.parse import urljoin

from django.conf import settings

def prepend_callback_base(url_path):
    """Prepend CALLBACK_BASE_URL to url_path.
    
    If we are running at a sub-URL (settings.FORCE_SCRIPT_NAME is set) then the prefix is stripped,
    since the callback is done on a private interface (to localhost) not via the public WebLab address.
    """

    if hasattr(settings, 'FORCE_SCRIPT_NAME') and settings.FORCE_SCRIPT_NAME is not None:
         url_path = url_path.replace(settings.FORCE_SCRIPT_NAME, '', 1)
    return urljoin(settings.CALLBACK_BASE_URL, url_path)
