import csv
import io
from collections import OrderedDict

from entities.models import ModelEntity, ModelGroup, ProtocolEntity
from experiments.models import Experiment, ExperimentVersion, Runnable
from repocache.models import CachedModelVersion, CachedProtocolVersion


def get_experiment_versions(user, cachedprotocolversion, cachedmodelversion_pks):
    """Retreives the experiment versions relating to a user, model(group) version and protocol version combination. """
    # experiment is visible if model & protocol are visible
    return (e.latest_version for e in Experiment.objects.filter(model_version__pk__in=cachedmodelversion_pks,
                                                                protocol_version=cachedprotocolversion,
                                                                model__in=ModelEntity.objects.visible_to_user(user),
                                                                protocol__in=ProtocolEntity.objects.visible_to_user(user))
            if e.latest_result == Runnable.STATUS_SUCCESS)



def get_url(experiment_versions):
    """Returns formatted experiment versions t use in a url """
    return '/' + '/'.join(str(ver.pk) for ver in experiment_versions)

def get_model_version_pks(mk):
    """Retreives the pks of model versions encoded in the mk stringe. """
    model_version_pks = set()
    models = ModelEntity.objects.none()
    if isinstance(mk, str):
        mk = mk.split('_')
    for model_or_group in filter(None, mk):
        if model_or_group.startswith('modelgroup'):
            model_or_group = int(model_or_group.replace('modelgroup', ''))
            models |=  ModelGroup.objects.get(pk=model_or_group).models.all()
        else:
            assert model_or_group.startswith('model'), "The model of group field value should start with model or modelgroup."+ model_or_group
            model_or_group = int(model_or_group.replace('model', ''))
            models |= ModelEntity.objects.filter(pk=model_or_group)
    return (m.repocache.latest_version.pk for m in models if m.repocache.versions.exists())

def get_versions_for_model_and_protocol(user, mk, pk):
    """Retreives the experiment versions relating to a user, model(group) and protocol combination. """
    if not pk or not mk:
        return ()

    protocol_version = ProtocolEntity.objects.get(pk=pk).repocache.latest_version.pk
    model_version_pks = get_model_version_pks(mk)
    return get_experiment_versions(user, protocol_version, model_version_pks)


def get_models_run_for_model_and_protocol(user, mk, pk):
    if not pk or not mk:
        return ()

    protocol_version = ProtocolEntity.objects.get(pk=pk).repocache.latest_version.pk
    model_version_pks = set()
    model_version_pks = get_model_version_pks(mk)
    return (e.model for e in Experiment.objects.filter(model_version__pk__in=model_version_pks, protocol_version=protocol_version) if e.latest_result == Runnable.STATUS_SUCCESS and e.is_visible_to_user(user))



def get_graph_file_names(user, mk, pk):
    """Retreives the file names of graphs for a given user, model(group) and protocol."""
    experiment_versions = get_versions_for_model_and_protocol(user, mk, pk)
    graph_files = OrderedDict()
    for experimentver in experiment_versions:
        try:
            plots_data_file = experimentver.open_file('outputs-default-plots.csv').read().decode("utf-8")
            plots_data_stream = io.StringIO(plots_data_file)
            for row in csv.DictReader(plots_data_stream):
                graph_files[(row['Data file name'], row['Data file name'])] = True
        except (FileNotFoundError, KeyError):
            pass  # This experiemnt version has no graphs
    return graph_files.keys()


def get_modelgroups(user):
    """ Returns the available model(group)s for a given user."""
    return [('', '--------- model group')] +\
           [('modelgroup' + str(modelgroup.pk), modelgroup.title) for modelgroup in ModelGroup.objects.all()
            if modelgroup.visible_to_user(user)] +\
           [('', '--------- model')] +\
           [('model' + str(model.pk), model.name)
            for model in ModelEntity.objects.visible_to_user(user)
            if model.repocache.versions.exists()]


def get_used_groups(user, model_key, protocol_key):
    """ Returns the model groups that are in use by a given model, protocol combination."""
    models = get_models_run_for_model_and_protocol(user, model_key, protocol_key)
    return set().union(*(m.model_groups.all() for m in models))


def get_protocols(mk, user):
    """ Returns the available protocols for given user and model(group)."""
    models = ModelGroup.objects.none()

    if isinstance(mk, str):
        mk = mk.split('_')

    for model_or_group in mk:
        if model_or_group.startswith('modelgroup'):
            model_or_group = int(model_or_group.replace('modelgroup', ''))
            models |= ModelGroup.objects.get(pk=model_or_group).models.all()
        elif model_or_group.startswith('model'):
            model_or_group = int(model_or_group.replace('model', ''))
            models |= ModelEntity.objects.filter(pk=model_or_group)

    if not models.exists():
        return []

    selected_model_pks = models.values_list('pk', flat=True)
    latest_model_versions_visible_pk = CachedModelVersion.objects.visible_to_user(user) \
                                                                 .order_by('entity', '-timestamp') \
                                                                 .values_list('pk', flat=True) \
                                                                 .distinct('entity')

    latest_protocol_versions_visible_pks = CachedProtocolVersion.objects.visible_to_user(user) \
                                                                .order_by('entity', '-timestamp') \
                                                                .values_list('pk', flat=True) \
                                                                .distinct('entity')

    succesful_experiment_pks = ExperimentVersion.objects.filter(status=Runnable.STATUS_SUCCESS) \
                                                .prefetch_related('experiment__pk') \
                                                .values_list('experiment__pk', flat=True)

    experiments = Experiment.objects.filter(pk__in=succesful_experiment_pks,
                                            model__pk__in=selected_model_pks,
                                            model_version__pk__in=latest_model_versions_visible_pk,
                                            protocol_version__pk__in=latest_protocol_versions_visible_pks) \
                                    .prefetch_related('protocol, protocol__pk, protocol__name')

    return experiments.order_by('protocol__pk').values_list('protocol__pk', 'protocol__name', flat=False).distinct()
