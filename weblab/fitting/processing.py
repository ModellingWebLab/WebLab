import logging
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.core.urlresolvers import reverse

from experiments.processing import submit_runnable

from .models import FittingResult, FittingResultVersion


logger = logging.getLogger(__name__)


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
    }

    return submit_runnable(version, body, user)
