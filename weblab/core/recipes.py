from model_mommy.recipe import Recipe, foreign_key, seq


user = Recipe('accounts.User', institution='UCL')

model = Recipe(
    'ModelEntity',
    visibility='public', entity_type='model', name=seq('mymodel')
)
protocol = Recipe(
    'ProtocolEntity',
    visibility='public', entity_type='protocol', name=seq('myprotocol')
)

model_file = Recipe('EntityFile', entity=foreign_key(model))
protocol_file = Recipe('EntityFile', entity=foreign_key(protocol))

experiment = Recipe(
    'Experiment',
    model=foreign_key(model),
    protocol=foreign_key(protocol)
)
experiment_version = Recipe(
    'ExperimentVersion',
    experiment=foreign_key(experiment),
    visibility='public'
)
