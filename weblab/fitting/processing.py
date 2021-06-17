import logging
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned
from django.urls import reverse
from core.processing import prepend_callback_base


from experiments.processing import submit_runnable

from .models import FittingResult, FittingResultVersion


logger = logging.getLogger(__name__)


def submit_fitting(
    model_version,
    protocol_version,
    fittingspec_version,
    dataset, user, rerun_ok,
):
    """Submit a Celery task to run a fitting experiment

    @param rerun_ok  if False and a FittingResultVersion already exists, will just return that.
        Otherwise will create a new version of the fitting result.
    @return the FittingResultVersion for the run
    """
    fittingresult, _ = FittingResult.objects.get_or_create(
        model=model_version.model,
        protocol=protocol_version.protocol,
        fittingspec=fittingspec_version.fittingspec,
        dataset=dataset,
        model_version=model_version,
        protocol_version=protocol_version,
        fittingspec_version=fittingspec_version,
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
        args=['model', model_version.model.pk, model_version.sha]
    )
    protocol_url = reverse(
        'entities:entity_archive',
        args=['protocol', protocol_version.protocol.pk, protocol_version.sha]
    )
    fittingspec_url = reverse(
        'fitting:entity_archive',
        args=['spec', fittingspec_version.fittingspec.pk, fittingspec_version.sha]
    )
    dataset_url = reverse(
        'datasets:archive',
        args=[dataset.pk]
    )

#    if hasattr(settings, 'FORCE_SCRIPT_NAME'):
#        model_url = model_url.replace(settings.FORCE_SCRIPT_NAME, '')
#        protocol_url = protocol_url.replace(settings.FORCE_SCRIPT_NAME, '')
#        fittingspec_url = fittingspec_url.replace(settings.FORCE_SCRIPT_NAME, '')
#        dataset_url = dataset_url.replace(settings.FORCE_SCRIPT_NAME, '')
    body = {
        'model': prepend_callback_base(model_url),
        'protocol': prepend_callback_base(protocol_url),
        'fittingSpec': prepend_callback_base(fittingspec_url),
        'dataset': prepend_callback_base(dataset_url),
    }

    submit_runnable(version, body, user)
    return version, True
