import logging

import requests

from core.processing import prepend_callback_base
from django.conf import settings
from django.db import IntegrityError
from django.urls import reverse
from experiments.models import PlannedExperiment
from repocache.models import ProtocolInterface, ProtocolIoputs

from .models import AnalysisTask, ModelEntity, ProtocolEntity


logger = logging.getLogger(__name__)


ERROR_FILE_NAME = 'errors.txt'


def submit_check_protocol_task(protocol, protocol_version):
    """Perform static checks of a new protocol version.

    This is called when a user creates a new version of a protocol,
    and kicks off a Celery task to perform various static checks of
    the protocol.

    At present, these check the syntax is correct, and if it is, extract
    the protocol's 'interface', i.e. the set of ontology terms by which
    it expects to interact with models, and the inputs and outputs for the
    protocol itself.

    :param protocol: the ``Protocol`` object
    :param protocol_version: the new version SHA just created
    """
    # If we've already analysed this protocol, this should be a no-op
    cached_version = protocol.repocache.get_version(protocol_version)
    if ProtocolIoputs.objects.filter(protocol_version=cached_version, kind=ProtocolIoputs.FLAG).exists():
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
        'getProtoInterface': prepend_callback_base(protocol_url),
        'signature': signature,
        'callBack': prepend_callback_base(reverse('entities:protocol_check_callback')),
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
        * ``ioputs``: if success, a list of {'name', 'units', 'kind'} objects detailing the inputs & outputs to
          the protocol
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
        if 'required' not in data or 'optional' not in data or 'ioputs' not in data:
            return {'error': 'missing terms'}
        cached_version = entity.repocache.get_version(version)
        cached_version.parsed_ok = True
        cached_version.interface.all().delete()  # Remove results of any previous analysis
        cached_version.save()
        terms = [
            ProtocolInterface(protocol_version=cached_version, term=term, optional=False)
            for term in data['required']
        ] + [
            ProtocolInterface(protocol_version=cached_version, term=term, optional=True)
            for term in data['optional']
        ]
        try:
            ProtocolInterface.objects.bulk_create(terms)
        except IntegrityError as e:
            return {'error': 'duplicate term provided: ' + str(e)}
        kinds = {name: value for value, name in ProtocolIoputs.KIND_CHOICES}
        ioputs = [
            ProtocolIoputs(
                protocol_version=cached_version,
                name=ioput['name'],
                units=ioput['units'],
                kind=kinds[ioput['kind']])
            for ioput in data['ioputs']
        ]
        # Store a flag so we know the interface has been analysed
        ioputs.append(ProtocolIoputs(protocol_version=cached_version, name=' ', kind=ProtocolIoputs.FLAG))
        try:
            ProtocolIoputs.objects.bulk_create(ioputs)
        except IntegrityError as e:
            return {'error': 'duplicate input or output provided: ' + str(e)}
    else:
        # Store error message as an ephemeral file
        error_message = data.get('returnmsg', '').replace('<br/>', '\n')
        if not error_message:
            return {'error': 'no error message supplied'}
        commit = entity.repo.get_commit(version)

        if ERROR_FILE_NAME in commit.filenames:
            logger.warning('Error file already exists in commit. New error message is: %s', error_message)
        else:
            content = b'Error analysing protocol:\n\n' + error_message.encode('UTF-8')
            commit.add_ephemeral_file(ERROR_FILE_NAME, content)
        # Don't try to analyse this protocol again
        cached_version = entity.repocache.get_version(version)
        cached_version.parsed_ok = False
        cached_version.save()
        ProtocolIoputs(protocol_version=cached_version, name=' ', kind=ProtocolIoputs.FLAG).save()

    return {}


def record_experiments_to_run(user, entity, commit):
    """Record what experiments to run automatically on a new entity version.

    Find all experiments run with the entity for which we're adding a new version (consider case of a model)
    Get the list of corresponding protocol IDs. We now know both our model ID, and all protocols that have
    previously had any version run on any version of this model.
    Run our new model version under the latest (visible) version of all those protocols.

    :param user: the user that created the new version
    :param entity: the entity that has had a new version created
    :param commit: the `Commit` object for the new version
    """
    new_version_kwargs = {
        entity.entity_type: entity,
        entity.entity_type + '_version': commit.sha,
    }
    if entity.other_type == entity.ENTITY_TYPE_MODEL:
        other_model = ModelEntity
    else:
        other_model = ProtocolEntity
    search_args = {
        entity.other_type + '_experiments__' + entity.entity_type: entity,
    }
    other_entities = other_model.objects.visible_to_user(user).filter(**search_args)
    for other_entity in other_entities:
        # Look for latest visible version
        for other_version in other_entity.cachedentity.versions.all():
            if other_entity.is_version_visible_to_user(other_version.sha, user):
                # Record the new experiment to run
                kwargs = {
                    'submitter': user,
                    entity.other_type: other_entity,
                    entity.other_type + '_version': other_version.sha,
                }
                kwargs.update(new_version_kwargs)
                PlannedExperiment.objects.get_or_create(**kwargs)
                break
