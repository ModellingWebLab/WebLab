import logging

import requests
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import transaction

from core import visibility

from .models import Experiment, ExperimentVersion


logger = logging.getLogger(__name__)


class ProcessingException(Exception):
    pass


@transaction.atomic
def submit_experiment(model, protocol, user):
    experiment, _ = Experiment.objects.get_or_create(
        model=model,
        protocol=protocol,
        defaults={
            'author': user,
            'visibility': visibility.get_joint_visibility(model.visibility, protocol.visibility)
        }
    )

    version = ExperimentVersion.objects.create(
        experiment=experiment,
        author=user,
        model_version=model.repo.latest_commit.hexsha,
        protocol_version=protocol.repo.latest_commit.hexsha
    )

    signature = str(version.abs_path)
    model_url = reverse(
        'entities:entity_archive',
        args=['model', model.pk, version.model_version]
    )
    protocol_url = reverse(
        'entities:entity_archive',
        args=['protocol', protocol.pk, version.protocol_version]
    )
    body = {
        'model': settings.BASE_URL + model_url,
        'protocol': settings.BASE_URL + protocol_url,
        'signature': signature,
        'callBack': settings.BASE_URL,
        'user': user.full_name,
        'password': settings.CHASTE_PASSWORD,
        'isAdmin': user.is_staff,
    }

    response = requests.post(settings.CHASTE_URL, body)

    res = response.content.decode().strip()
    logger.debug('Response from chaste backend: %s' % res)

    if not res.startswith(signature):
        logger.error('Chaste backend answered with something unexpected: %s' % res)
        raise ProcessingException(res)

    status = res[len(signature):].strip()

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
