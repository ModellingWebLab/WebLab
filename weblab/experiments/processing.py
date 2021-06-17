import logging
import zipfile
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.urls import reverse
from django.utils.timezone import now
from core.processing import prepend_callback_base

from .emails import send_experiment_finished_email
from .models import (
    Experiment,
    ExperimentVersion,
    Runnable,
    RunningExperiment,
)


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


def submit_runnable(runnable, body, user):
    """Submit a Celery task to the Chaste backend

    @param runnable Runnable object to submit
    @param body dict of extra parameters to post to the request
    @param user user making the request
    """
    run = RunningExperiment.objects.create(runnable=runnable)
    signature = runnable.signature

    body.update({
        'signature': runnable.signature,
        'callBack': prepend_callback_base(reverse('experiments:callback')),
        'user': user.full_name,
        'password': settings.CHASTE_PASSWORD,
        'isAdmin': user.is_staff,
    })

    try:
        response = requests.post(settings.CHASTE_URL, body)
    except requests.exceptions.ConnectionError:
        run.delete()
        runnable.status = Runnable.STATUS_FAILED
        runnable.return_text = 'Unable to connect to experiment runner service'
        runnable.save()
        logger.exception(runnable.return_text)
        return runnable, True

    res = response.content.decode().strip()
    logger.debug('Response from chaste backend: %s' % res)

    if not res.startswith(signature):
        run.delete()
        runnable.status = Runnable.STATUS_FAILED
        runnable.return_text = 'Chaste backend answered with something unexpected: %s' % res
        runnable.save()
        logger.error(runnable.return_text)
        raise ProcessingException(res)

    status = res[len(signature):].strip()

    if status.startswith('succ'):
        run.task_id = status[4:].strip()
        run.save()
    elif status == 'inapplicable':
        run.delete()
        runnable.status = Runnable.STATUS_INAPPLICABLE
    else:
        run.delete()
        logger.error('Chaste backend answered with error: %s' % status)
        runnable.status = Runnable.STATUS_FAILED
        runnable.return_text = status

    runnable.save()


def submit_experiment(model_version, protocol_version, user, rerun_ok):
    """Submit a Celery task to run an experiment.

    @param rerun_ok  if False and an ExperimentVersion already exists, will just return that.
        Otherwise will create a new version of the experiment.
    @return the ExperimentVersion for the run
    """
    experiment, _ = Experiment.objects.get_or_create(
        model=model_version.model,
        protocol=protocol_version.protocol,
        model_version=model_version,
        protocol_version=protocol_version,
        defaults={
            'author': user,
        }
    )

    # Check there isn't an existing version if we're not allowed to re-run
    if not rerun_ok:
        try:
            version, created = ExperimentVersion.objects.get_or_create(
                experiment=experiment,
                defaults={
                    'author': user,
                }
            )
        except MultipleObjectsReturned:
            return ExperimentVersion.objects.filter(experiment=experiment).latest('created_at'), False
        if not created:
            return version, False
    else:
        version = ExperimentVersion.objects.create(
            experiment=experiment,
            author=user,
        )

    model_url = reverse(
        'entities:entity_archive',
        args=['model', model_version.model.pk, model_version.sha]
    )
    protocol_url = reverse(
        'entities:entity_archive',
        args=['protocol', protocol_version.protocol.pk, protocol_version.sha]
    )

    body = {
        'model': prepend_callback_base(model_url),
        'protocol': prepend_callback_base(protocol_url),
    }

    submit_runnable(version, body, user)
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
        exp = run.runnable
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
