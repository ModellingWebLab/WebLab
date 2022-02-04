import shutil
from pathlib import Path

import pytest
from django.urls import reverse
from guardian.shortcuts import assign_perm, remove_perm

from core import recipes
from experiments.models import Experiment
from stories.models import Story, StoryGraph, StoryText
from stories.views import get_experiment_versions, get_url


@pytest.fixture
def experiment_with_result_public_no_file(experiment_with_result):
    experiment = experiment_with_result.experiment
    # make sure protocol / models are visible
    experiment.model_version.visibility = 'public'
    experiment.protocol_version.visibility = 'public'
    experiment.model_version.save()
    experiment.protocol_version.save()
    return experiment_with_result


@pytest.fixture
def experiment_with_result_public(experiment_with_result_public_no_file):
    # add graphs
    experiment_with_result_public_no_file.mkdir()
    shutil.copy(Path(__file__).absolute().parent.joinpath('./test.omex'),
                experiment_with_result_public_no_file.archive_path)

    return experiment_with_result_public_no_file

@pytest.mark.django_db
class TestStoryCreateView:
    @pytest.fixture
    def models(self, logged_in_user, helpers):
        models = []
        # want to make sure ids from models, protocols and experiments are unique
        # to avoid being able to assign wrong objects
        for i in range(5): #range(5):
            models.append(recipes.model.make(author=logged_in_user, id=100 + i))
        return models

    @pytest.fixture
    def experiment_versions(self, logged_in_user, helpers, models):
        # make some models and protocols
        protocols = []
        # make sure ids are unique
        for i in range(3): #range(30):
            protocols.append(recipes.protocol.make(author=logged_in_user, id=200 + i))
        exp_versions = []

        # add some versions and add experiment versions
        for model in models:
            helpers.add_version(model, visibility='private')
            # for the last protocol add another experiment version
            for protocol in protocols + [protocols[-1]]:
                helpers.add_version(protocol, visibility='public')
                exp_version = recipes.experiment_version.make(
                    status='SUCCESS',
                    experiment__model=model,
                    experiment__model_version=model.repocache.latest_version,
                    experiment__protocol=protocol,
                    experiment__protocol_version=protocol.repocache.latest_version)
                exp_version.mkdir()
                with (exp_version.abs_path / 'result.txt').open('w') as f:
                    f.write('experiment results')

                # add graphs
                exp_version.mkdir()
                shutil.copy(Path(__file__).absolute().parent.joinpath('./test.omex'), exp_version.archive_path)
                exp_versions.append(exp_version)
        return exp_versions

    def test_get_protocol_via_modelgroup(self, experiment_versions, models, client, logged_in_user, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment
        modelgroup = recipes.modelgroup.make(author=logged_in_user, models=[experiment.model, experiment_versions[0].experiment.model])

        for i in range(1, len(models)-1):#rem
            recipes.modelgroup.make(author=logged_in_user, models=[models[i], models[i+1]])
        from guardian.shortcuts import assign_perm
        assign_perm('edit_entity', logged_in_user, experiment.protocol)


        import timeit
        from entities.models import ModelGroup, ModelEntity, ProtocolEntity
        from repocache.models import CachedModelVersion, CachedModel, CachedProtocolVersion, CachedProtocol
        from django.db.models import Prefetch
        from experiments.models import (Experiment, ExperimentVersion, ProtocolEntity, Runnable)
        from guardian.shortcuts import get_objects_for_user
        def method1(modelgroup):
            return [m.repocache.latest_version.pk
                    for m in ModelGroup.objects.get(pk=modelgroup.pk).models.all()
                    if m.repocache.versions.count()]


        def get_protocol1(modelgroup, logged_in_user):
            model_version_pks = method1(modelgroup)
            return set((e.protocol.pk, e.protocol.name)
                       for e in Experiment.objects.filter(model_version__pk__in=model_version_pks)
                       if e.latest_result == Runnable.STATUS_SUCCESS and
                       e.is_visible_to_user(logged_in_user))

        def get_protocol2(modelgroup, logged_in_user):
            models = ModelGroup.objects.get(pk=modelgroup.pk).models.all()
            selected_model_pks = models.values_list('pk', flat=True)
            latest_model_versions_visible_to_user_pk = CachedModelVersion.objects.visible_to_user(logged_in_user).order_by('entity', '-timestamp').values_list('pk', flat=True).distinct('entity')
            latest_protocol_versions_visible_to_user_pks = CachedProtocolVersion.objects.visible_to_user(logged_in_user).order_by('entity', '-timestamp').values_list('pk', flat=True).distinct('entity')
            succesful_experiment_pks = ExperimentVersion.objects.filter(status=Runnable.STATUS_SUCCESS) \
                                                        .prefetch_related('experiment__pk') \
                                                        .values_list('experiment__pk', flat=True)
            experiments = Experiment.objects.filter(pk__in=succesful_experiment_pks,
                                                    model__pk__in=selected_model_pks,
                                                    model_version__pk__in=latest_model_versions_visible_to_user_pk,
                                                    protocol_version__pk__in=latest_protocol_versions_visible_to_user_pks) \
                                            .prefetch_related('protocol, protocol__pk, protocol__name')
            return experiments.order_by('protocol__pk').values_list('protocol__pk', 'protocol__name', flat=False).distinct()



        protocol2 = get_protocol2(modelgroup, logged_in_user)
        protocol1 = get_protocol1(modelgroup, logged_in_user)
#        assert sorted(protocol1) == sorted(protocol2)

        time_protocol2 = timeit.Timer(lambda: get_protocol2(modelgroup, logged_in_user)).timeit(10)
        time_protocol1 = timeit.Timer(lambda: get_protocol1(modelgroup, logged_in_user)).timeit(10)
        assert False, str((time_protocol1, time_protocol2, protocol1, protocol2))


