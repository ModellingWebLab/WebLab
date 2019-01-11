import logging
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.urlresolvers import reverse

from repocache.models import ProtocolInterface

from .models import AnalysisTask


logger = logging.getLogger(__name__)


ERROR_FILE_NAME = 'errors.txt'


def submit_check_protocol_task(protocol, protocol_version):
    """Perform static checks of a new protocol version.

    This is called when a user creates a new version of a protocol,
    and kicks off a Celery task to perform various static checks of
    the protocol.

    At present, these check the syntax is correct, and if it is, extract
    the protocol's 'interface', i.e. the set of ontology terms by which
    it expects to interact with models.

    :param protocol: the ``Protocol`` object
    :param protocol_version: the new version just created
    """
    # If we've already analysed this protocol, this should be a no-op
    cached_version = protocol.repocache.get_version(protocol_version)
    if ProtocolInterface.objects.filter(protocol_version=cached_version).exists():
        return

    # Submit the analysis task
    task = AnalysisTask.objects.create(
        entity=protocol,
        version=protocol_version
    )
    signature = task.id
    protocol_url = reverse(
        'entities:entity_archive',
        args=['protocol', protocol.pk, protocol_version]
    )
    body = {
        'getProtoInterface': urljoin(settings.CALLBACK_BASE_URL, protocol_url),
        'signature': signature,
        'callBack': urljoin(settings.CALLBACK_BASE_URL, reverse('entities:protocol_check_callback')),
        'password': settings.CHASTE_PASSWORD,
    }

    try:
        response = requests.post(settings.CHASTE_URL, body)
    except requests.exceptions.ConnectionError:
        task.delete()
        logger.exception('Unable to connect to protocol checking service')
        return

    res = response.content.decode().strip()
    logger.debug('Response from protocol checking service: %s' % res)

    if res:
        # Empty response indicates success, so this is an error
        task.delete()


def process_check_protocol_callback(data):
    """Process the callback response from a protocol checking task.

    Will create an ephemeral errors file in case of problems, and record the interface in the DB on success.

    :param data: a single JSON object with fields:
        * ``signature``: identifier as supplied when the task was launched
        * ``returntype``: 'success' or 'failed'
        * ``returnmsg``: if failed, an error string formatted with simple HTML (`br` tags only)
        * ``required``: if success, a list of strings (the required ontology terms in the protocol's interface)
        * ``optional``: if success, a list of strings (the optional ontology terms in the protocol's interface)
    :returns: a JSON callback response object, with fields:
        * ``error``: an error message iff there was a problem
    """
    signature = data.get('signature')
    if not signature:
        return {'error': 'missing signature'}
    try:
        task = AnalysisTask.objects.get(id=signature)
    except AnalysisTask.DoesNotExist:
        return {'error': 'invalid signature'}

    entity = task.entity
    version = task.version
    task.delete()  # So it can be re-run later if desired, and keep the table small

    if 'returntype' not in data:
        return {'error': 'missing returntype'}
    success = data['returntype'] == 'success'

    if success:
        # Store protocol interface in the repocache
        if 'required' not in data or 'optional' not in data:
            return {'error': 'missing terms'}
        cached_version = entity.repocache.get_version(version)
        terms = [
            ProtocolInterface(protocol_version=cached_version, term=term, optional=False)
            for term in data['required']
        ] + [
            ProtocolInterface(protocol_version=cached_version, term=term, optional=True)
            for term in data['optional']
        ]
        if not terms:
            # Store a blank term so we know the interface has been analysed
            terms.append(ProtocolInterface(protocol_version=cached_version, term='', optional=True))
        ProtocolInterface.objects.bulk_create(terms)
    else:
        # Store error message as an ephemeral file
        error_message = data.get('returnmsg', '')
        if not error_message:
            return {'error': 'no error message supplied'}
        commit = entity.repo.get_commit(version)

        if ERROR_FILE_NAME in commit.filenames:
            logger.warning('Error file already exists in commit. New error message is: %s', error_message)

        content = b'Error analysing protocol:\n\n' + error_message.encode('UTF-8')
        commit.add_ephemeral_file(ERROR_FILE_NAME, content)

    return {}
