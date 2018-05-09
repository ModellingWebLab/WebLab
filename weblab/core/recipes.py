from model_mommy.recipe import Recipe, seq


user = Recipe('accounts.User', institution='UCL')

model = Recipe(
    'ModelEntity',
    visibility='public', entity_type='model', name=seq('mymodel')
)
protocol = Recipe(
    'ProtocolEntity',
    visibility='public', entity_type='protocol', name=seq('myprotocol')
)

model_file = Recipe('EntityFile', entity=model.make)
protocol_file = Recipe('EntityFile', entity=protocol.make)

experiment = Recipe('Experiment', model=model.make, protocol=protocol.make)
experiment_version = Recipe('ExperimentVersion', experiment=experiment.make, visibility='public')
