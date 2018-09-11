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

model_file = Recipe('EntityFile', entity=foreign_key(model))
protocol_file = Recipe('EntityFile', entity=foreign_key(protocol))

experiment = Recipe(
    'Experiment',
    model=foreign_key(model),
    protocol=foreign_key(protocol)
)

running_experiment = Recipe('RunningExperiment')

experiment_version = Recipe('ExperimentVersion', experiment=foreign_key(experiment))
