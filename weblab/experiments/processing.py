import logging
import zipfile
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.core.urlresolvers import reverse
from django.utils.timezone import now

from .emails import send_experiment_finished_email
from .models import Experiment, Runnable, RunningExperiment


logger = logging.getLogger(__name__)


class ChasteProcessingStatus:
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    INAPPLICABLE = "inapplicable"

    MODEL_STATUSES = {
        SUCCESS: Runnable.STATUS_SUCCESS,
        RUNNING: Runnable.STATUS_RUNNING,
        PARTIAL: Runnable.STATUS_PARTIAL,
        FAILED: Runnable.STATUS_FAILED,
        INAPPLICABLE: Runnable.STATUS_INAPPLICABLE,
    }

    @classmethod
    def get_model_status(cls, status):
        return cls.MODEL_STATUSES.get(status)


class ProcessingException(Exception):
    pass


def submit_experiment(model, model_version, protocol, protocol_version, user, rerun_ok):
    """Submit a Celery task to run an experiment.

    @param rerun_ok  if False and an ExperimentVersion already exists, will just return that.
        Otherwise will create a new version of the experiment.
    @return the ExperimentVersion for the run
    """
    experiment, _ = Experiment.objects.get_or_create(
        model=model,
        protocol=protocol,
        model_version=model.repocache.get_version(model_version),
        protocol_version=protocol.repocache.get_version(protocol_version),
        defaults={
            'author': user,
        }
    )

    # Check there isn't an existing version if we're not allowed to re-run
    if not rerun_ok:
        try:
            version, created = Runnable.objects.get_or_create(
                experiment=experiment,
                defaults={
                    'author': user,
                }
            )
        except MultipleObjectsReturned:
            return Runnable.objects.filter(experiment=experiment).latest('created_at'), False
        if not created:
            return version, False
    else:
        version = Runnable.objects.create(
            experiment=experiment,
            author=user,
        )

    run = RunningExperiment.objects.create(experiment_version=version)
    signature = version.signature

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
        'signature': signature,
        'callBack': urljoin(settings.CALLBACK_BASE_URL, reverse('experiments:callback')),
        'user': user.full_name,
        'password': settings.CHASTE_PASSWORD,
        'isAdmin': user.is_staff,
    }
    if protocol.is_fitting_spec:
        body['dataset'] = body['fittingSpec'] = body['protocol']

    try:
        response = requests.post(settings.CHASTE_URL, body)
    except requests.exceptions.ConnectionError:
        run.delete()
        version.status = Runnable.STATUS_FAILED
        version.return_text = 'Unable to connect to experiment runner service'
        version.save()
        logger.exception(version.return_text)
        return version, True

    res = response.content.decode().strip()
    logger.debug('Response from chaste backend: %s' % res)

    if not res.startswith(signature):
        run.delete()
        version.status = Runnable.STATUS_FAILED
        version.return_text = 'Chaste backend answered with something unexpected: %s' % res
        version.save()
        logger.error(version.return_text)
        raise ProcessingException(res)

    status = res[len(signature):].strip()

    if status.startswith('succ'):
        run.task_id = status[4:].strip()
        run.save()
    elif status == 'inapplicable':
        run.delete()
        version.status = Runnable.STATUS_INAPPLICABLE
    else:
        run.delete()
        logger.error('Chaste backend answered with error: %s' % status)
        version.status = Runnable.STATUS_FAILED
        version.return_text = status

    version.save()

    return version, True


def cancel_experiment(task_id):
    """Cancel the Celery task for an experiment.

    @param task_id  the Celery task id of the experiment to cancel
    """
    body = {
        'cancelTask': task_id,
        'password': settings.CHASTE_PASSWORD,
    }

    try:
        requests.post(settings.CHASTE_URL, body)
    except requests.exceptions.ConnectionError:
        logger.exception("Unable to cancel experiment")


def process_callback(data, files):
    signature = data.get('signature')
    if not signature:
        return {'error': 'missing signature'}

    try:
        run = RunningExperiment.objects.get(id=signature)
        exp = run.experiment_version
    except RunningExperiment.DoesNotExist:
        return {'error': 'invalid signature'}

    task_id = data.get('taskid')
    if task_id:
        run.task_id = task_id
        run.save()

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
    if exp.is_finished:
        exp.finished_at = now()

    exp.save()

    if exp.is_finished or exp.status == Runnable.STATUS_INAPPLICABLE:
        # We unset the task_id to ensure the delete() below doesn't send a message to the back-end cancelling
        # the task, causing it to be killed while still sending us its 'finished' message!
        run.task_id = ''
        run.delete()

    if exp.is_finished:
        send_experiment_finished_email(exp)

        if not files.get('experiment'):
            exp.update(Runnable.STATUS_FAILED,
                       '%s (backend returned no archive)' % exp.return_text)
            return {'error': 'no archive found'}

        exp.mkdir()
        with exp.archive_path.open('wb+') as dest:
            for chunk in files['experiment'].chunks():
                dest.write(chunk)

        # Make sure it's a valid zip
        try:
            zipfile.ZipFile(str(exp.archive_path))
        except zipfile.BadZipFile as e:
            exp.update(Runnable.STATUS_FAILED, 'error reading archive: %s' % e)
            return {'experiment': 'failed'}

        return {'experiment': 'ok'}

    return {}
