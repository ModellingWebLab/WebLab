import shutil
from pathlib import Path

import pytest
from django import forms
from guardian.shortcuts import assign_perm, remove_perm

from core import recipes
from stories.forms import (
    StoryCollaboratorForm,
    StoryForm,
    StoryGraphForm,
    StoryGraphFormSet,
    StoryTextForm,
    StoryTextFormSet,
)
from stories.models import Story, StoryGraph, StoryText


@pytest.fixture
def experiment_with_result_public(experiment_with_result):
    experiment = experiment_with_result.experiment
    # make sure protocol / models are visible
    experiment.model_version.visibility = 'public'
    experiment.protocol_version.visibility = 'public'
    experiment.model_version.save()
    experiment.protocol_version.save()
    return experiment_with_result


@pytest.mark.django_db
class TestStoryCollaboratorForm:
    def _form(self, data, entity, **kwargs):
        form = StoryCollaboratorForm(data, entity=entity, **kwargs)
        form.fields['DELETE'] = forms.BooleanField(required=False)
        return form

    def test_loads_collaborator_from_email(self, user, story):
        form = self._form({}, story, initial={'email': user.email})
        assert form.collaborator == user

    def test_stores_entity_object(self, story):
        form = self._form({}, story)
        assert form.entity == story

    def test_get_user_returns_none_if_not_found(self, story):
        form = self._form({}, story)
        assert form.entity == story
        assert form._get_user('nonexistent@example.com') is None

    def test_loads_user_from_email(self, logged_in_user, other_user, experiment_with_result):
        experiment = experiment_with_result.experiment
        story = recipes.story.make(author=logged_in_user)
        recipes.story_text.make(author=logged_in_user, story=story)
        recipes.story_graph.make(author=story.author, story=story, cachedprotocolversion=experiment.protocol_version,
                                 cachedmodelversions=[experiment.model_version], models=[experiment.model])
        form = self._form({'email': other_user.email, 'DELETE': False}, story)
        assert not form.is_valid()

        experiment.protocol_version.visibility = 'public'
        experiment.protocol_version.save()
        assert experiment.protocol_version.protocol.is_version_visible_to_user(experiment.protocol_version.sha,
                                                                               other_user)
        form = self._form({'email': other_user.email, 'DELETE': False}, story)
        assert not form.is_valid()

        experiment.model_version.visibility = 'public'
        experiment.model_version.save()
        assert experiment.model_version.model.is_version_visible_to_user(experiment.model_version.sha, other_user)

        form = self._form({'email': other_user.email, 'DELETE': False}, story)
        assert form.is_valid()
        assert form.cleaned_data['user'] == other_user
        assert form.cleaned_data['email'] == other_user.email

    def test_raises_validation_error_on_non_existent_email(self, story):
        form = self._form({'email': 'nonexistent@example.com'}, story)
        assert not form.is_valid()
        assert 'email' in form.errors

    def test_add_collaborator(self, logged_in_user, experiment_with_result, other_user):
        experiment = experiment_with_result.experiment
        story = recipes.story.make(author=logged_in_user, visibility='private')
        recipes.story_text.make(author=logged_in_user, story=story)
        recipes.story_graph.make(author=story.author, story=story, cachedprotocolversion=experiment.protocol_version,
                                 cachedmodelversions=[experiment.model_version], models=[experiment.model])
        assert not other_user.has_perm('edit_story', story)

        experiment.protocol_version.visibility = 'public'
        experiment.model_version.visibility = 'public'
        experiment.protocol_version.save()
        experiment.model_version.save()

        form = self._form({'email': other_user.email, 'DELETE': False}, story)
        assert form.is_valid()
        form.add_collaborator()
        assert other_user.has_perm('edit_story', story)

    def test_cant_add_author_as_collaborator(self, story):
        form = self._form({'email': story.author.email, 'DELETE': False}, story)
        assert not form.is_valid()

    def test_remove_collaborator(self, experiment_with_result, logged_in_user, other_user):
        experiment = experiment_with_result.experiment
        story = recipes.story.make(author=logged_in_user, visibility='private')
        recipes.story_text.make(author=logged_in_user, story=story)
        recipes.story_graph.make(author=story.author, story=story, cachedprotocolversion=experiment.protocol_version,
                                 cachedmodelversions=[experiment.model_version], models=[experiment.model])
        experiment.protocol_version.visibility = 'public'
        experiment.model_version.visibility = 'public'
        experiment.protocol_version.save()
        experiment.model_version.save()

        assign_perm('edit_story', other_user, story)
        assert other_user.has_perm('edit_story', story)
        form = self._form({'email': other_user.email, 'DELETE': True}, story)
        assert form.is_valid()
        form.remove_collaborator()
        assert not other_user.has_perm('edit_story', story)


@pytest.mark.django_db
class TestStoryTextFormSet:
    def test_create_storyText(self, story):
        story_text_count = StoryText.objects.count()
        form = StoryTextForm(user=story.author, data={})
        assert form.is_valid()
        form = StoryTextForm(user=story.author, data={'description': 'simple text example', 'ORDER': '0'})
        form.delete()  # should do nothing, as no existing text loaded
        story_text = form.save(story)
        assert StoryText.objects.count() == story_text_count + 1
        assert story_text.story == story
        assert story_text.description == 'simple text example'
        assert story_text.order == 0

    def test_load_storyText(self, story):
        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading')
        form = StoryTextForm(user=story.author, data={'description': story_text.description, 'pk': story_text.pk})
        assert form.is_valid()
        assert form.cleaned_data['description'] == 'test loading'

    def test_edit_storyText(self, story):
        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading', order=12)
        story_text_count = StoryText.objects.count()
        form = StoryTextForm(user=story.author, instance=story_text,
                             data={'description': 'edited story text', 'ORDER': story_text.order,
                                   'pk': story_text.pk, 'number': 0})
        form.save(story)
        assert StoryText.objects.count() == story_text_count  # not created an extra one
        assert story_text.story == story
        assert story_text.description == 'edited story text'

    def test_delete_storyText(self, story):
        story_text_count = StoryText.objects.count()
        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading', order=12)
        assert StoryText.objects.count() == story_text_count + 1
        data = {'description': 'edited story text', 'ORDER': story_text.order, 'pk': story_text.pk, 'number': 0}
        form = StoryTextForm(user=story.author, instance=story_text, data=data, initial=data)
        assert form.is_valid()
        form.delete()
        assert StoryText.objects.count() == story_text_count

    def test_create_storyText_via_formset(self, story):
        story_text_count = StoryText.objects.count()
        form_kwargs = {'user': story.author}
        post_data = {'text-TOTAL_FORMS': 1, 'text-INITIAL_FORMS': 1, 'text-MIN_NUM_FORMS': 0,
                     'text-MAX_NUM_FORMS': 1000, 'text-0-ORDER': 0, 'text-0-description': 'new story text item'}
        formset = StoryTextFormSet(post_data, prefix='text', initial=[{'ORDER': 0, 'number': 0}],
                                   form_kwargs=form_kwargs)
        assert formset.is_valid()
        new_texts = formset.save(story)
        assert StoryText.objects.count() == story_text_count + 1
        assert len(new_texts) == 1
        assert new_texts[0].story == story
        assert new_texts[0].author == story.author
        assert new_texts[0].description == 'new story text item'
        assert new_texts[0].order == 0

    def test_edit_storyText_via_formset(self, story):
        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading', order=12)
        story_text_count = StoryText.objects.count()
        form_kwargs = {'user': story.author}
        post_data = {'text-TOTAL_FORMS': 1, 'text-INITIAL_FORMS': 1, 'text-MIN_NUM_FORMS': 0,
                     'text-MAX_NUM_FORMS': 1000, 'text-0-ORDER': 0, 'text-0-description': 'edited descr'}
        formset = StoryTextFormSet(post_data, prefix='text', initial=[{'ORDER': 0, 'number': 0,
                                   'pk': story_text.pk, 'description': 'edited descr'}], form_kwargs=form_kwargs)
        assert formset.is_valid()
        new_texts = formset.save(story)
        assert StoryText.objects.count() == story_text_count
        assert len(new_texts) == 1
        assert new_texts[0] == story_text
        assert new_texts[0].story == story
        assert new_texts[0].author == story.author
        assert new_texts[0].description == 'edited descr'
        assert new_texts[0].order == 0

    def test_delete_storyText_via_formset(self, story):
        story_text_count = StoryText.objects.count()
        form_kwargs = {'user': story.author}
        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading', order=12)
        assert StoryText.objects.count() == story_text_count + 1
        post_data = {'text-TOTAL_FORMS': 1, 'text-INITIAL_FORMS': 1, 'text-MIN_NUM_FORMS': 0,
                     'text-MAX_NUM_FORMS': 1000, 'text-0-ORDER': story_text.order,
                     'text-0-DELETE': 'true'}
        formset = StoryTextFormSet(post_data, prefix='text',
                                   initial=[{'ORDER': story_text.order, 'DELETE': True,
                                             'number': 0, 'pk': story_text.pk,
                                             'description': 'test loading'}], form_kwargs=form_kwargs)
        assert StoryText.objects.count() == story_text_count + 1
        formset.save(story)
        assert StoryText.objects.count() == story_text_count


@pytest.mark.django_db
class TestStoryGraphFormSet:
    @pytest.fixture
    def experiment(self, experiment_with_result_public):
        experiment_with_result_public.mkdir()
        shutil.copy(Path(__file__).absolute().parent.joinpath('./test.omex'),
                    experiment_with_result_public.archive_path)
        return experiment_with_result_public.experiment

    def test_missing_fields_storyGraph(self, experiment, story, model_with_version, protocol_with_version):
        data = {'ORDER': '0', 'number': 0, 'currentGraph': '', 'update': 'True'}

        form = StoryGraphForm(data=data, user=story.author)
        assert not form.is_valid()

        data['id_models'] = str([experiment.model.pk])
        form = StoryGraphForm(data=data, user=story.author)
        assert not form.is_valid()

        data['id_models'] = ['model' + str(experiment.model.pk)]
        form = StoryGraphForm(data=data, user=story.author)
        assert not form.is_valid()

        data['protocol'] = str(experiment.protocol.pk)
        form = StoryGraphForm(data=data, user=story.author)
        assert not form.is_valid()

        data['graphfiles'] = 'outputs_APD90_gnuplot_data.csv'
        form = StoryGraphForm(data=data, user=story.author)
        assert form.is_valid()

    def test_create_storyGraph(self, experiment, story, model_with_version, protocol_with_version):
        story_graph_count = StoryGraph.objects.count()
        modelgroup, modelgroup2, modelgroup3 = recipes.modelgroup.make(models=[model_with_version],
                                                                       visibility='public', _quantity=3)

        data = {'ORDER': '0',
                'number': 0,
                'currentGraph': '', 'update': 'True', 'id_models':
                ['model' + str(experiment.model.pk), f'modelgroup{modelgroup.pk}'],
                'protocol': str(experiment.protocol.pk),
                'grouptoggles': [modelgroup2.pk, modelgroup3.pk],
                'graphfilename': 'outputs_APD90_gnuplot_data.csv',
                'graphfiles': 'outputs_APD90_gnuplot_data.csv'}

        form = StoryGraphForm(data=data, user=story.author)
        assert story_graph_count == StoryGraph.objects.count()
        form.delete()  # should do nothing, as no existing graph loaded
        assert StoryGraph.objects.count() == story_graph_count

        story_graph = form.save(story)
        assert StoryGraph.objects.count() == story_graph_count + 1
        assert story_graph.story == story
        assert story_graph.order == 0
        assert list(story_graph.cachedmodelversions.all()) == [experiment.model_version]
        assert story_graph.cachedprotocolversion == experiment.protocol_version
        assert list(story_graph.models.all()) == [experiment.model]
        assert set(story_graph.grouptoggles.all()) == set([modelgroup2, modelgroup3])
        assert list(story_graph.modelgroups.all()) == [modelgroup]
        assert story_graph.graphfilename == 'outputs_APD90_gnuplot_data.csv'

    def test_load_storyGraph(self, experiment, story):
        story_graph = recipes.story_graph.make(author=story.author, story=story,
                                               cachedprotocolversion=experiment.protocol_version,
                                               cachedmodelversions=[experiment.model_version],
                                               models=[experiment.model], order=1)
        story_graph_count = StoryGraph.objects.count()
        data = {'ORDER': '1', 'number': 0,
                'currentGraph': str(story_graph), 'update': 'True',
                'id_models': ['model' + str(experiment.model.pk)],
                'protocol': str(experiment.protocol.pk),
                'graphfiles': 'outputs_APD90_gnuplot_data.csv',
                'graphfilename': 'outputs_APD90_gnuplot_data.csv', 'pk': story_graph.pk}
        form = StoryGraphForm(data=data, user=story.author, instance=story_graph)

        assert form.is_valid()
        assert form.cleaned_data['ORDER'] == 1
        assert form.cleaned_data['currentGraph'] == str(story_graph)
        assert form.cleaned_data['update'] == 'True'
        assert form.cleaned_data['id_models'] == ['model' + str(experiment.model.pk)]
        assert form.cleaned_data['protocol'] == str(experiment.protocol.pk)
        assert form.cleaned_data['graphfiles'] == 'outputs_APD90_gnuplot_data.csv'
        assert StoryGraph.objects.count() == story_graph_count

    def test_edit_storyGraph(self, experiment, story):
        story_graph = recipes.story_graph.make(author=story.author, story=story,
                                               cachedprotocolversion=experiment.protocol_version,
                                               cachedmodelversions=[experiment.model_version],
                                               models=[experiment.model], order=1,
                                               graphfilename='outputs_APD90_gnuplot_data.csv')
        story_graph_count = StoryGraph.objects.count()

        # only update order
        data = {'ORDER': '2', 'number': 1, 'currentGraph': str(story_graph), 'update': '', 'id_models':
                ['model' + str(experiment.model.pk)],
                'protocol': str(experiment.protocol.pk),
                'graphfilename': 'outputs_Resting_potential_gnuplot_data.csv',
                'graphfiles': 'outputs_Resting_potential_gnuplot_data.csv', 'pk': story_graph.pk}
        form = StoryGraphForm(data=data, user=story.author, instance=story_graph)
        form.save(story)
        assert story_graph.author == story.author
        assert story_graph.story == story
        assert story_graph.order == 2
        assert story_graph.cachedprotocolversion == experiment.protocol_version
        assert list(story_graph.cachedmodelversions.all()) == [experiment.model_version]
        assert story_graph.graphfilename == 'outputs_APD90_gnuplot_data.csv'
        assert StoryGraph.objects.count() == story_graph_count

        # update full graph
        data['update'] = 'True'
        form = StoryGraphForm(data=data, user=story.author, instance=story_graph)
        form.save(story)
        assert story_graph.author == story.author
        assert story_graph.story == story
        assert story_graph.order == 2
        assert story_graph.cachedprotocolversion == experiment.protocol_version
        assert list(story_graph.cachedmodelversions.all()) == [experiment.model_version]
        assert story_graph.graphfilename == 'outputs_Resting_potential_gnuplot_data.csv'
        assert StoryGraph.objects.count() == story_graph_count

    def test_delete_storyGraph(self, experiment, story):
        story_graph = recipes.story_graph.make(author=story.author, story=story,
                                               cachedprotocolversion=experiment.protocol_version,
                                               cachedmodelversions=[experiment.model_version],
                                               models=[experiment.model], order=1,
                                               graphfilename='outputs_Resting_potential_gnuplot_data.csv')
        story_graph_count = StoryGraph.objects.count()

        data = {'id_models': ['model' + str(story_graph.cachedmodelversions.first().model.pk)],
                'protocol': story_graph.cachedprotocolversion.protocol.pk, 'graphfiles': story_graph.graphfilename,
                'graphfilename': story_graph.graphfilename, 'order': 0,
                'currentGraph': str(story_graph), 'ORDER': story_graph.order, 'pk': story_graph.pk}

        form = StoryGraphForm(user=story.author, instance=story_graph, data=data, initial=data)
        assert form.is_valid()
        form.delete()
        assert StoryGraph.objects.count() == story_graph_count - 1

    def test_create_storyGraph_via_formset(self, experiment, story):
        modelgroup = recipes.modelgroup.make(author=story.author, models=[experiment.model_version.model],
                                             title='test model group', visibility='public')

        story_graph_count = StoryGraph.objects.count()
        form_kwargs = {'user': story.author}
        post_data = {'graph-TOTAL_FORMS': 1, 'graph-INITIAL_FORMS': 0, 'graph-MIN_NUM_FORMS': 0,
                     'graph-MAX_NUM_FORMS': 1000, 'graph-0-ORDER': '10', 'graph-0-currentGraph': '',
                     'graph-0-update': 'True', 'graph-0-id_models': ['modelgroup' + str(modelgroup.pk)],
                     'graph-0-protocol': str(experiment.protocol.pk),
                     'graph-0-graphfiles': 'outputs_APD90_gnuplot_data.csv'}

        formset = StoryGraphFormSet(post_data, prefix='graph', initial=[{'ORDER': '', 'currentGraph': ''}],
                                    form_kwargs=form_kwargs)
        new_graphs = formset.save(story)
        assert StoryGraph.objects.count() == story_graph_count + 1
        assert len(new_graphs) == 1
        assert new_graphs[0].order == 10
        assert list(new_graphs[0].modelgroups.all()) == [modelgroup]
        assert new_graphs[0].story == story
        assert new_graphs[0].author == story.author
        assert new_graphs[0].cachedprotocolversion == experiment.protocol_version
        assert list(new_graphs[0].cachedmodelversions.all()) == [experiment.model_version]
        assert new_graphs[0].graphfilename == 'outputs_APD90_gnuplot_data.csv'

    def test_edit_storyGraph_via_formset(self, experiment, story):
        modelgroup = recipes.modelgroup.make(author=story.author, models=[experiment.model],
                                             title='test model group', visibility='public')

        story_graph = recipes.story_graph.make(author=story.author, story=story,
                                               cachedprotocolversion=experiment.protocol_version,
                                               modelgroups=[modelgroup],
                                               order=0, cachedmodelversions=[experiment.model_version],
                                               graphfilename='outputs_Resting_potential_gnuplot_data.csv')
        story_graph_count = StoryGraph.objects.count()
        form_kwargs = {'user': story.author}

        # only update order
        post_data = {'graph-TOTAL_FORMS': 1, 'graph-INITIAL_FORMS': 1, 'graph-MIN_NUM_FORMS': 0,
                     'graph-MAX_NUM_FORMS': 1000, 'graph-0-ORDER': 10,
                     'graph-0-currentGraph': str(story_graph), 'graph-0-update': '',
                     'graph-0-id_models': [f'modelgroup{mg.pk}' for mg in story_graph.modelgroups.all()],
                     'graph-0-protocol': str(story_graph.cachedprotocolversion.protocol.pk),
                     'graph-0-graphfiles': 'outputs_APD90_gnuplot_data.csv'}

        initial = [{'id_models': [f'modelgroup{mg.pk}' for mg in story_graph.modelgroups.all()],
                    'protocol': story_graph.cachedprotocolversion.protocol.pk,
                    'graphfiles': story_graph.graphfilename, 'currentGraph': str(story_graph),
                    'ORDER': story_graph.order, 'pk': story_graph.pk}]

        formset = StoryGraphFormSet(post_data, prefix='graph', initial=initial, form_kwargs=form_kwargs)
        new_graphs = formset.save(story)
        assert StoryGraph.objects.count() == story_graph_count
        assert len(new_graphs) == 1
        assert new_graphs[0].order == 10
        assert list(new_graphs[0].modelgroups.all()) == [modelgroup]
        assert new_graphs[0].story == story
        assert new_graphs[0].author == story.author
        assert new_graphs[0].cachedprotocolversion == experiment.protocol_version
        assert list(new_graphs[0].cachedmodelversions.all()) == [experiment.model_version]
        assert new_graphs[0].graphfilename == 'outputs_Resting_potential_gnuplot_data.csv'

        # update full graph
        post_data['graph-0-update'] = 'True'
        formset = StoryGraphFormSet(post_data, prefix='graph', initial=initial, form_kwargs=form_kwargs)
        new_graphs = formset.save(story)

        assert StoryGraph.objects.count() == story_graph_count
        assert len(new_graphs) == 1
        assert new_graphs[0].order == 10
        assert list(new_graphs[0].modelgroups.all()) == [modelgroup]
        assert new_graphs[0].story == story
        assert new_graphs[0].author == story.author
        assert new_graphs[0].cachedprotocolversion == experiment.protocol_version
        assert list(new_graphs[0].cachedmodelversions.all()) == [experiment.model_version]
        assert new_graphs[0].graphfilename == 'outputs_APD90_gnuplot_data.csv'

    def test_delete_storyGraph_via_formset(self, experiment, story):
        modelgroup = recipes.modelgroup.make(author=story.author, models=[experiment.model_version.model],
                                             title='test model group', visibility='public')

        story_graph = recipes.story_graph.make(author=story.author, story=story,
                                               cachedprotocolversion=experiment.protocol_version,
                                               modelgroups=[modelgroup],
                                               order=0, cachedmodelversions=[experiment.model_version],
                                               graphfilename='outputs_Resting_potential_gnuplot_data.csv')
        story_graph_count = StoryGraph.objects.count()
        form_kwargs = {'user': story.author}
        # only update order
        post_data = {'graph-TOTAL_FORMS': 1, 'graph-INITIAL_FORMS': 1, 'graph-MIN_NUM_FORMS': 0,
                     'graph-MAX_NUM_FORMS': 1000, 'graph-0-ORDER': 10, 'graph-0-DELETE': 'True'}

        initial = [{'id_models': [f'modelgroup{mg.pk}' for mg in story_graph.modelgroups.all()],
                    'protocol': story_graph.cachedprotocolversion.protocol.pk,
                    'graphfiles': story_graph.graphfilename, 'currentGraph': str(story_graph),
                    'graphfilename': story_graph.graphfilename,
                    'ORDER': story_graph.order, 'order': 0, 'pk': story_graph.pk}]

        formset = StoryGraphFormSet(post_data, prefix='graph', initial=initial, form_kwargs=form_kwargs)
        formset.save(story)
        assert StoryGraph.objects.count() == story_graph_count - 1


@pytest.mark.django_db
class TestStoryForm:
    def test_invalid_fields_story(self, logged_in_user, story):
        assign_perm('entities.moderator', logged_in_user)
        form = StoryForm(user=logged_in_user, data={})
        assert str(form.fields['visibility'].choices) == \
            "[('private', 'Private'), ('public', 'Public'), ('moderated', 'Moderated')]"
        assert not form.is_valid()  # missing form fields

        form = StoryForm(user=story.author, instance=story,
                         data={'title': story.title, 'visibility': 'public', 'graphvisualizer': 'displayPlotFlot'})
        form.num_parts = 1
        assert form.is_valid()  # can save existing item

        form = StoryForm(user=story.author,
                         data={'title': story.title, 'visibility': 'public', 'graphvisualizer': 'displayPlotFlot'})
        assert not form.is_valid()  # duplicate title

        recipes.story.make(author=story.author, title='additional story')
        form = StoryForm(data={'title': 'additional story', 'visibility': 'public',
                         'graphvisualizer': 'displayPlotFlot'}, user=story.author, instance=story)
        assert not form.is_valid()  # duplicate title

    def test_create_story(self, logged_in_user):
        story_count = Story.objects.count()
        remove_perm('entities.moderator', logged_in_user)
        form = StoryForm(user=logged_in_user, data={'title': 'new test story', 'visibility': 'public',
                                                    'graphvisualizer': 'displayPlotFlot'})
        assert str(form.fields['visibility'].choices) == "[('private', 'Private'), ('public', 'Public')]"
        form.num_parts = 1
        assert form.is_valid()
        story = form.save()
        assert Story.objects.count() == story_count + 1
        assert story.author == logged_in_user
        assert story.title == 'new test story'

    def test_load_story(self, story):
        form = StoryForm(user=story.author, instance=story, data={'title': story.title, 'visibility': story.visibility,
                                                                  'graphvisualizer': story.graphvisualizer})
        form.num_parts = 1
        assert form.is_valid()
        assert form.cleaned_data['title'] == story.title
        assert form.cleaned_data['visibility'] == story.visibility
        assert form.cleaned_data['graphvisualizer'] == story.graphvisualizer

    def test_edit_story_invalid(self, story):
        form = StoryForm(user=story.author, instance=story, data={'title': '', 'visibility': 'private',
                                                                  'graphvisualizer': 'displayPlotHC'})
        form.num_parts = 1
        assert not form.is_valid()

    def test_edit_story(self, story):
        form = StoryForm(user=story.author, instance=story, data={'title': 'new title', 'visibility': 'private',
                                                                  'graphvisualizer': 'displayPlotHC'})
        form.num_parts = 1
        assert form.is_valid()
        assert form.save()

    def test_edit_story_no_parts(self, story):
        form = StoryForm(user=story.author, instance=story, data={'title': 'new title', 'visibility': 'private',
                                                                  'graphvisualizer': 'displayPlotHC'})
        form.num_parts = 0
        assert not form.is_valid()  # No text of graphs
