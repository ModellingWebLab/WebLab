import logging
import zipfile
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import transaction

from .emails import send_experiment_finished_email
from .models import Experiment, ExperimentVersion


logger = logging.getLogger(__name__)


class ChasteProcessingStatus:
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    INAPPLICABLE = "inapplicable"

    MODEL_STATUSES = {
        SUCCESS: ExperimentVersion.STATUS_SUCCESS,
        RUNNING: ExperimentVersion.STATUS_RUNNING,
        PARTIAL: ExperimentVersion.STATUS_PARTIAL,
        FAILED: ExperimentVersion.STATUS_FAILED,
        INAPPLICABLE: ExperimentVersion.STATUS_INAPPLICABLE,
    }

    @classmethod
    def get_model_status(cls, status):
        return cls.MODEL_STATUSES.get(status)


class ProcessingException(Exception):
    pass


@transaction.atomic
def submit_experiment(model, model_version, protocol, protocol_version, user):
    experiment, _ = Experiment.objects.get_or_create(
        model=model,
        protocol=protocol,
        model_version=model_version,
        protocol_version=protocol_version,
        defaults={
            'author': user,
        }
    )

    version = ExperimentVersion.objects.create(
        experiment=experiment,
        author=user,
    )

    model_url = reverse(
        'entities:entity_archive',
        args=['model', model.pk, model_version]
    )
    protocol_url = reverse(
        'entities:entity_archive',
        args=['protocol', protocol.pk, protocol_version]
    )
    body = {
        'model': urljoin(settings.CALLBACK_BASE_URL, model_url),
        'protocol': urljoin(settings.CALLBACK_BASE_URL, protocol_url),
        'signature': version.signature,
        'callBack': urljoin(settings.CALLBACK_BASE_URL, reverse('experiments:callback')),
        'user': user.full_name,
        'password': settings.CHASTE_PASSWORD,
        'isAdmin': user.is_staff,
    }

    try:
        response = requests.post(settings.CHASTE_URL, body)
    except requests.exceptions.ConnectionError:
        version.status = ExperimentVersion.STATUS_FAILED
        version.return_text = 'Unable to connect to experiment runner service'
        logger.exception(version.return_text)
        version.save()
        return version

    res = response.content.decode().strip()
    logger.debug('Response from chaste backend: %s' % res)

    if not res.startswith(version.signature):
        logger.error('Chaste backend answered with something unexpected: %s' % res)
        raise ProcessingException(res)

    status = res[len(version.signature):].strip()

    if status.startswith('succ'):
        version.task_id = status[4:].strip()
    elif status == 'inapplicable':
        version.status = ExperimentVersion.STATUS_INAPPLICABLE
    else:
        logger.error('Chaste backend answered with error: %s' % res)
        version.status = ExperimentVersion.STATUS_FAILED
        version.return_text = status

    version.save()

    return version


def process_callback(data, files):
    signature = data.get('signature')
    if not signature:
        return {'error': 'missing signature'}

    try:
        exp = ExperimentVersion.objects.get(id=signature)
    except ExperimentVersion.DoesNotExist:
        return {'error': 'invalid signature'}

    task_id = data.get('taskid')
    if task_id:
        exp.task_id = task_id

    if 'returntype' not in data:
        return {'error': 'missing returntype'}

    status = ChasteProcessingStatus.get_model_status(data['returntype'])
    if status:
        exp.status = status
    else:
        return {'error': 'invalid returntype'}

    exp.return_text = data.get('returnmsg') or 'finished'
    if exp.is_running:
        exp.return_text = 'running'

    exp.save()

    if exp.is_finished:
        send_experiment_finished_email(exp)

        if not files.get('experiment'):
            exp.update(ExperimentVersion.STATUS_FAILED,
                       '%s (backend returned no archive)' % exp.return_text)
            return {'error': 'no archive found'}

        exp.abs_path.mkdir(exist_ok=True)
        with exp.archive_path.open('wb+') as dest:
            for chunk in files['experiment'].chunks():
                dest.write(chunk)

        # Make sure it's a valid zip
        try:
            zipfile.ZipFile(str(exp.archive_path))
        except zipfile.BadZipFile as e:
            exp.update(ExperimentVersion.STATUS_FAILED, 'error reading archive: %s' % e)
            return {'experiment': 'failed'}

        return {'experiment': 'ok'}

    return {}
