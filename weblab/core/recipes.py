from model_mommy.recipe import Recipe, foreign_key, seq


user = Recipe('accounts.User', institution='UCL', full_name=seq('test user '))

model = Recipe(
    'ModelEntity',
    entity_type='model', name=seq('my model')
)
protocol = Recipe(
    'ProtocolEntity',
    entity_type='protocol', name=seq('my protocol')
)
fittingspec = Recipe(
    'FittingSpec',
    entity_type='fittingspec', name=seq('my spec'),
    protocol=foreign_key(protocol),
)

model_file = Recipe('EntityFile', entity=foreign_key(model))
protocol_file = Recipe('EntityFile', entity=foreign_key(protocol))

analysis_task = Recipe('AnalysisTask', entity=foreign_key(protocol))

cached_model = Recipe('CachedModel')
cached_model_version = Recipe('CachedModelVersion')
cached_model_tag = Recipe('CachedModelTag')

cached_protocol = Recipe('CachedProtocol')
cached_protocol_version = Recipe('CachedProtocolVersion')
cached_protocol_tag = Recipe('CachedProtocolTag')

cached_fittingspec = Recipe('CachedFittingSpec')
cached_fittingspec_version = Recipe('CachedFittingSpecVersion')
cached_fittingspec_tag = Recipe('CachedFittingSpecTag')

experiment = Recipe(
    'Experiment',
    model=foreign_key(model),
    model_version=foreign_key(cached_model_version),
    protocol=foreign_key(protocol),
    protocol_version=foreign_key(cached_protocol_version),
)

runnable = Recipe('Runnable')

experiment_version = Recipe('ExperimentVersion', experiment=foreign_key(experiment))

running_experiment = Recipe('RunningExperiment', runnable=foreign_key(runnable))


dataset = Recipe('Dataset',
                 name=seq('my dataset'),
                 protocol=foreign_key(protocol))

dataset_file = Recipe('DatasetFile',
                      dataset=foreign_key(dataset))

fittingresult = Recipe(
    'FittingResult',
    model=foreign_key(model),
    model_version=foreign_key(cached_model_version),
    protocol=foreign_key(protocol),
    protocol_version=foreign_key(cached_protocol_version),
    fittingspec=foreign_key(fittingspec),
    fittingspec_version=foreign_key(cached_fittingspec_version),
    dataset=foreign_key(dataset),
)

fittingresult_version = Recipe('FittingResultVersion', fittingresult=foreign_key(fittingresult))
