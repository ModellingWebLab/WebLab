import pytest

from core import recipes
from entities.models import ModelGroup
from stories.models import Story, StoryGraph, StoryText


@pytest.mark.django_db
def test_story(user, other_user):
    # make
    story = recipes.story.make(author=user, title='test title', visibility='private')
    assert story.author == user
    assert story.title == 'test title'
    assert Story.objects.count() == 1
    assert story.visible_to_user(user)
    assert not story.visible_to_user(other_user)
    assert story.is_editable_by(user)
    assert not story.is_editable_by(other_user)

    # change
    story.author = other_user
    story.title = 'new title'
    story.visibility = 'public'
    story.save()
    assert story.author == other_user
    assert story.title == str(story) == 'new title'
    assert Story.objects.count() == 1
    assert story.visible_to_user(user)
    assert story.visible_to_user(other_user)
    assert not story.is_editable_by(user)
    assert story.is_editable_by(other_user)

    # delete
    story.delete()
    assert Story.objects.count() == 0


@pytest.mark.django_db
def test_make_storytext(user, other_user):
    stories = recipes.story.make(author=user, _quantity=2)

    # make
    story_text = recipes.story_text.make(author=user, description='test descr', story=stories[0], order=1)
    assert story_text.author == user
    assert story_text.story == stories[0]
    assert story_text.order == 1
    assert story_text.description == str(story_text) == 'test descr'
    assert StoryText.objects.count() == 1

    # change
    story_text.author = other_user
    story_text.story = stories[1]
    story_text.order = 0
    story_text.description = 'new descr'
    story_text.save()
    assert story_text.author == other_user
    assert story_text.story == stories[1]
    assert story_text.order == 0
    assert story_text.description == str(story_text) == 'new descr'
    assert StoryText.objects.count() == 1

    # delete via cascade on story
    stories[1].delete()
    assert StoryText.objects.count() == 0


@pytest.mark.django_db
def test_make_storygraph(user, other_user, experiment_with_result, model_with_version, public_model, public_protocol):
    stories = recipes.story.make(author=user, _quantity=2)
    experiment = experiment_with_result.experiment

    # make
    story_graph = recipes.story_graph.make(author=user, story=stories[0],
                                           cachedprotocolversion=experiment.protocol_version,
                                           order=0, cachedmodelversions=[experiment.model_version],
                                           models=[experiment.model],
                                           graphfilename='outputs_Transmembrane_voltage_gnuplot_data.csv')
    assert story_graph.author == user
    assert story_graph.story == stories[0]
    assert story_graph.order == 0
    assert story_graph.cachedprotocolversion == experiment.protocol_version
    assert list(story_graph.cachedmodelversions.all()) == [experiment.model_version]
    assert story_graph.graphfilename == 'outputs_Transmembrane_voltage_gnuplot_data.csv'
    assert StoryGraph.objects.count() == 1

    # change
    modelgroup = recipes.modelgroup.make(author=user, models=[model_with_version, public_model],
                                         title="test model group")
    story_graph.author = other_user
    story_graph.story = stories[1]
    story_graph.cachedprotocolversion = public_protocol.repocache.latest_version
    story_graph.order = 3
    story_graph.modelgroup = modelgroup
    story_graph.cachedmodelversions.set([m.repocache.latest_version for m in modelgroup.models.all()])
    story_graph.graphfilename = 'outputs_All_state_variables_gnuplot_data.csv'
    story_graph.save()
    assert story_graph.author == other_user
    assert story_graph.story == stories[1]
    assert story_graph.order == 3
    assert story_graph.cachedprotocolversion == public_protocol.repocache.latest_version
    assert sorted([m.model for m in story_graph.cachedmodelversions.all()], key=str) ==\
        sorted([model_with_version, public_model], key=str)
    assert story_graph.modelgroup == modelgroup
    assert story_graph.graphfilename == 'outputs_All_state_variables_gnuplot_data.csv'
    assert StoryGraph.objects.count() == 1

    # delete via cascade on story
    stories[1].delete()
    assert StoryGraph.objects.count() == 0


@pytest.mark.django_db
def test_user_cannot_have_same_named_story(story, other_user):
    # another user can create a story with the same title
    assert story.author != other_user
    recipes.story.make(author=other_user, title=story.title)


@pytest.mark.django_db
def test_delete_model(story):
    assert StoryGraph.objects.count() == 1
    graph = StoryGraph.objects.filter(story=story).first()
    graph.cachedmodelversions.first().model.delete()
    assert StoryGraph.objects.count() == 0


@pytest.mark.django_db
def test_delete_group(story):
    assert StoryGraph.objects.count() == 1
    graph = StoryGraph.objects.filter(story=story).first()
    model = graph.cachedmodelversions.first().model
    assert ModelGroup.objects.count() == 0
    recipes.modelgroup.make(models=[model])
    assert ModelGroup.objects.count() == 1
    model.delete()
    assert ModelGroup.objects.count() == 0
