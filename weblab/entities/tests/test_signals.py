import pytest
from core import recipes
from entities.models import ModelEntity, ModelGroup
from accounts.models import User
from stories.models import Story, StoryGraph


@pytest.mark.django_db
def test_story(helpers, user, experiment_with_result):
    experiment = experiment_with_result.experiment

    num_users = User.objects.count()
    num_models = ModelEntity.objects.count()
    num_model_groups = ModelGroup.objects.count()
    num_stories = Story.objects.count()
    num_graphs = StoryGraph.objects.count()

    new_user = recipes.user.make()
    model = experiment.model_version.model

    model.author = new_user
    model.save()

    modelgroup = recipes.modelgroup.make(author=new_user, models=[model],
                                         title="test model group")

    story = recipes.story.make(author=user, title='test title', visibility='private')

    recipes.story_graph.make(author=user, story=story, cachedprotocolversion=experiment.protocol_version,
                             cachedmodelversions=[experiment.model_version], modelgroup=modelgroup)

    recipes.story_graph.make(author=user, story=story, cachedprotocolversion=experiment.protocol_version,
                             cachedmodelversions=[experiment.model_version])

    # make sure repo path exists (even if we haven't stored any files in it)
    model.repo_abs_path.mkdir(parents=True, exist_ok=True)

    assert User.objects.count() == num_users + 1
    assert ModelEntity.objects.count() == num_models
    assert ModelGroup.objects.count() == num_model_groups + 1
    assert Story.objects.count() == num_stories + 1
    assert StoryGraph.objects.count() == num_graphs + 2
    assert model.repo_abs_path.exists()

    new_user.delete()

    assert User.objects.count() == num_users
    assert ModelEntity.objects.count() == num_models - 1
    assert ModelGroup.objects.count() == num_model_groups
    assert Story.objects.count() == num_stories + 1
    assert StoryGraph.objects.count() == num_graphs
    assert not model.repo_abs_path.exists()

