#import pytest
#from django.test import TestCase
#
#from core import recipes
#
#
#@pytest.fixture
#def story(user):
#    return recipes.story.make(author=user)
#
#
#@pytest.fixture
#def story_text(user, story):
#    return recipes.story_text.make(author=user, story=story)
#
#
#@pytest.fixture
#def story_graph(user, story):
#    pass
#    return recipes.story_graph.make(author=user, story=story, graphfilename='outputs_Transmembrane_voltage_gnuplot_data.csv', 
#                                     cachedprotocolversion=cachedprotocolversion, cachedmodelversions=[cachedmodelversion])
#
#
#@pytest.mark.django_db
#class TestExperimentsDeletion:
#    def test_delete_experiment_in_use(self, story, story_text):
#        pass
#
# Create your tests here.
