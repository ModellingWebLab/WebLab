import logging
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.core.urlresolvers import reverse

from experiments.models import Runnable, RunningExperiment

from .models import FittingResult, FittingResultVersion


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


def submit_fitting(
    model, model_version,
    protocol, protocol_version,
    fittingspec, fittingspec_version,
    dataset, user, rerun_ok,
):
    """Submit a Celery task to run a fitting

    @param rerun_ok  if False and a FittingResultVersion already exists, will just return that.
        Otherwise will create a new version of the fitting result.
    @return the FittingResultVersion for the run
    """
    fittingresult, _ = FittingResult.objects.get_or_create(
        model=model,
        protocol=protocol,
        fittingspec=fittingspec,
        dataset=dataset,
        model_version=model.repocache.get_version(model_version),
        protocol_version=protocol.repocache.get_version(protocol_version),
        fittingspec_version=fittingspec.repocache.get_version(fittingspec_version),
        defaults={
            'author': user,
        }
    )

    # Check there isn't an existing version if we're not allowed to re-run
    if not rerun_ok:
        try:
            version, created = FittingResultVersion.objects.get_or_create(
                fittingresult=fittingresult,
                defaults={
                    'author': user,
                }
            )
        except MultipleObjectsReturned:
            return FittingResultVersion.objects.filter(fittingresult=fittingresult).latest('created_at'), False
        if not created:
            return version, False
    else:
        version = FittingResultVersion.objects.create(
            fittingresult=fittingresult,
            author=user,
        )

    run = RunningExperiment.objects.create(runnable=version)
    signature = version.signature

    model_url = reverse(
        'entities:entity_archive',
        args=['model', model.pk, model_version]
    )
    protocol_url = reverse(
        'entities:entity_archive',
        args=['protocol', protocol.pk, protocol_version]
    )
    fittingspec_url = reverse(
        'fitting:entity_archive',
        args=['spec', fittingspec.pk, fittingspec_version]
    )
    dataset_url = reverse(
        'datasets:archive',
        args=[dataset.pk]
    )
    body = {
        'model': urljoin(settings.CALLBACK_BASE_URL, model_url),
        'protocol': urljoin(settings.CALLBACK_BASE_URL, protocol_url),
        'fittingSpec': urljoin(settings.CALLBACK_BASE_URL, fittingspec_url),
        'dataset': urljoin(settings.CALLBACK_BASE_URL, dataset_url),
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
