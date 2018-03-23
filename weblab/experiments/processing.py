from django.db import transaction

from core import visibility

from .models import Experiment, ExperimentVersion


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

    return version
