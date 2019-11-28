from model_mommy.recipe import Recipe, foreign_key, seq


user = Recipe('accounts.User', institution='UCL')

model = Recipe(
    'ModelEntity',
    entity_type='model', name=seq('mymodel')
)
protocol = Recipe(
    'ProtocolEntity',
    entity_type='protocol', name=seq('myprotocol')
)
fittingspec = Recipe(
    'FittingSpec',
    entity_type='fittingspec', name=seq('myspec'),
    protocol=foreign_key(protocol),
)

model_file = Recipe('EntityFile', entity=foreign_key(model))
protocol_file = Recipe('EntityFile', entity=foreign_key(protocol))

analysis_task = Recipe('AnalysisTask', entity=foreign_key(protocol))

experiment = Recipe(
    'Experiment',
    model=foreign_key(model),
    protocol=foreign_key(protocol)
)

running_experiment = Recipe('RunningExperiment')

experiment_version = Recipe('ExperimentVersion', experiment=foreign_key(experiment))

cached_model = Recipe('CachedModel')
cached_model_version = Recipe('CachedModelVersion')
cached_model_tag = Recipe('CachedModelTag')

cached_protocol = Recipe('CachedProtocol')
cached_protocol_version = Recipe('CachedProtocolVersion')
cached_protocol_tag = Recipe('CachedProtocolTag')

dataset = Recipe('Dataset',
                 name=seq('mydataset'),
                 protocol=foreign_key(protocol))

dataset_file = Recipe('DatasetFile',
                      dataset=foreign_key(dataset))
