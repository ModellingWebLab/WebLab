import shutil
from pathlib import Path

import pytest
from django.urls import reverse
from guardian.shortcuts import assign_perm, remove_perm

from core import recipes
from entities.models import ProtocolEntity
from experiments.models import Experiment
from stories.models import Story, StoryGraph, StoryText
from stories.views import get_experiment_versions, get_url


@pytest.fixture
def experiment_with_result_public_no_file(experiment_with_result):
    experiment = experiment_with_result.experiment
    # make sure protocol / models are visible
    experiment.model_version.visibility = 'public'
    experiment.protocol_version.visibility = 'public'
    experiment.model_version.save()
    experiment.protocol_version.save()
    return experiment_with_result


@pytest.fixture
def experiment_with_result_public(experiment_with_result_public_no_file):
    # add graphs
    experiment_with_result_public_no_file.mkdir()
    shutil.copy(Path(__file__).absolute().parent.joinpath('./test.omex'),
                experiment_with_result_public_no_file.archive_path)

    return experiment_with_result_public_no_file


@pytest.mark.django_db
def test_get_experiment_versions_url(experiment_with_result_public):
    user = experiment_with_result_public.author
    cachedprotocolversion = experiment_with_result_public.experiment.protocol_version
    cachedmodelversion_pks = [experiment_with_result_public.experiment.model_version.pk]
    experiment_versions = tuple(get_experiment_versions(user, cachedprotocolversion, cachedmodelversion_pks))
    assert [v.pk for v in experiment_versions] == [experiment_with_result_public.pk]
    assert str(get_url(experiment_versions)) == '/' + str(experiment_with_result_public.pk)


@pytest.mark.django_db
def test_StoryListView(logged_in_user, other_user, client):
    stories = recipes.story.make(author=logged_in_user, _quantity=3)
    other_stories = recipes.story.make(author=other_user, _quantity=3, visibility='public')
    private_stories = recipes.story.make(author=other_user, _quantity=3, visibility='private')
    assign_perm('edit_story', logged_in_user, private_stories[0])

    response = client.get('/stories/')
    assert response.status_code == 200
    assert list(response.context['story_list']) == stories + other_stories + [private_stories[0]]


@pytest.mark.django_db
class TestStoryDeleteView:
    def test_owner_can_delete(self, logged_in_user, client, story):
        story_count = Story.objects.count()
        response = client.post('/stories/%d/delete' % story.pk)
        assert response.status_code == 302
        assert Story.objects.count() == story_count - 1

    def test_non_owner_cannot_delete(self, logged_in_user, other_user, client):
        story = recipes.story.make(author=other_user)
        story_count = Story.objects.count()
        response = client.post('/stories/%d/delete' % story.pk)
        assert response.status_code == 403
        assert Story.objects.count() == story_count


@pytest.mark.django_db
class TestStoryCollaboratorsView:
    def test_anonymous_cannot_view_page(self, client):
        story = recipes.story.make()
        response = client.get('/stories/%d/collaborators' % story.pk)
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_non_owner_cannot_view_page(self, logged_in_user, client):
        story = recipes.story.make()
        response = client.get('/stories/%d/collaborators' % story.pk)
        assert response.status_code == 403

    def test_owner_can_view_page(self, logged_in_user, client, story):
        response = client.get('/stories/%d/collaborators' % story.pk)
        assert response.status_code == 200
        assert 'formset' in response.context

    def test_superuser_can_view_page(self, logged_in_admin, client):
        story = recipes.story.make(visibility='private')
        response = client.get('/stories/%d/collaborators' % story.pk)
        assert response.status_code == 200
        assert 'formset' in response.context

    def test_loads_existing_collaborators(self, logged_in_user, other_user, client, story):
        assign_perm('edit_story', other_user, story)
        response = client.get('/stories/%d/collaborators' % story.pk)
        assert response.status_code == 200
        assert response.context['formset'][0]['email'].value() == other_user.email

    def test_add_editor(self, logged_in_user, other_user, helpers, client):
        helpers.add_permission(other_user, 'create_model')
        story = recipes.story.make(author=logged_in_user)
        response = client.post('/stories/%d/collaborators' % story.pk,
                               {
                                   'form-0-email': other_user.email,
                                   'form-TOTAL_FORMS': 1,
                                   'form-MAX_NUM_FORMS': 1,
                                   'form-MIN_NUM_FORMS': 0,
                                   'form-INITIAL_FORMS': 0,
                               })
        assert response.status_code == 302
        assert other_user.has_perm('edit_story', story)

    def test_add_non_existent_user_as_editor(self, logged_in_user, client, story):
        response = client.post('/stories/%d/collaborators' % story.pk,
                               {
                                   'form-0-email': 'non-existent@example.com',
                                   'form-TOTAL_FORMS': 1,
                                   'form-MAX_NUM_FORMS': 1,
                                   'form-MIN_NUM_FORMS': 0,
                                   'form-INITIAL_FORMS': 0,
                               })
        assert response.status_code == 200
        assert 'email' in response.context['formset'][0].errors

    def test_remove_editor(self, logged_in_user, other_user, helpers, client, story):
        helpers.add_permission(other_user, 'create_model')
        assign_perm('edit_story', other_user, story)
        response = client.post('/stories/%d/collaborators' % story.pk,
                               {
                                   'form-0-DELETE': 'on',
                                   'form-0-email': other_user.email,
                                   'form-TOTAL_FORMS': 1,
                                   'form-MAX_NUM_FORMS': 1,
                                   'form-MIN_NUM_FORMS': 0,
                                   'form-INITIAL_FORMS': 1,
                               })
        assert response.status_code == 302
        assert not other_user.has_perm('edit_story', story)

    def test_non_owner_cannot_edit(self, logged_in_user, client):
        story = recipes.story.make()
        response = client.post('/stories/%d/collaborators' % story.pk, {})
        assert response.status_code == 403

    def test_anonymous_cannot_edit(self, client):
        story = recipes.story.make()
        response = client.post('/stories/%d/collaborators' % story.pk, {})
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_superuser_can_edit(self, client, logged_in_admin, model_creator):
        story = recipes.story.make()
        response = client.post('/stories/%d/collaborators' % story.pk,
                               {
                                   'form-0-email': model_creator.email,
                                   'form-TOTAL_FORMS': 1,
                                   'form-MAX_NUM_FORMS': 1,
                                   'form-MIN_NUM_FORMS': 0,
                                   'form-INITIAL_FORMS': 0,
                               })
        assert response.status_code == 302
        assert model_creator.has_perm('edit_story', story)


@pytest.mark.django_db
class TestStoryTransferView:
    def test_transfer_success(self, client, logged_in_user, other_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        story = recipes.story.make(author=logged_in_user)

        story_count = Story.objects.count()
        assert story.author.email == 'test@example.com'
        response = client.post(
            '/stories/%d/transfer' % story.pk,
            data={
                'email': other_user.email,
            },
        )
        assert response.status_code == 302
        story.refresh_from_db()
        assert story.author == other_user
        assert Story.objects.count() == story_count

    def test_transfer_invalid_user(self, client, logged_in_user, other_user, helpers, story):
        helpers.add_permission(logged_in_user, 'create_model')

        story_count = Story.objects.count()
        assert story.author.email == 'test@example.com'
        response = client.post(
            '/stories/%d/transfer' % story.pk,
            data={
                'email': 'invalid@example.com',
            },
        )
        assert response.status_code == 200
        story.refresh_from_db()
        assert story.author == logged_in_user
        assert Story.objects.count() == story_count

    def test_transfer_other_user_has_same_named_entity(self, client, logged_in_user, other_user, helpers, story):
        helpers.add_permission(logged_in_user, 'create_model')
        recipes.story.make(author=other_user, title=story.title)

        story_count = Story.objects.count()
        assert story.author.email == 'test@example.com'
        response = client.post(
            '/stories/%d/transfer' % story.pk,
            data={
                'email': 'other@example.com',
            },
        )
        assert response.status_code == 200
        story.refresh_from_db()
        assert story.author == logged_in_user
        assert Story.objects.count() == story_count

    def test_transfer_other_user_has_no_access_to_group(self, client, logged_in_user, other_user, helpers, story):
        helpers.add_permission(logged_in_user, 'create_model')
        graph = StoryGraph.objects.filter(story=story).first()
        modelgroup = recipes.modelgroup.make(author=logged_in_user, visibility='private',
                                             models=[graph.cachedmodelversions.first().model])
        graph.modelgroups.add(modelgroup)
        graph.save()

        story_count = Story.objects.count()
        assert story.author.email == 'test@example.com'
        response = client.post(
            '/stories/%d/transfer' % story.pk,
            data={
                'email': 'other@example.com',
            },
        )
        assert response.status_code == 200
        story.refresh_from_db()
        assert story.author == logged_in_user
        assert Story.objects.count() == story_count

    def test_transfer_other_user_has_no_access_to_protocol_version(self, client, logged_in_user, other_user, helpers,
                                                                   story):
        helpers.add_permission(logged_in_user, 'create_model')
        graph = StoryGraph.objects.filter(story=story).first()
        graph.cachedprotocolversion.visibility = 'private'
        graph.cachedprotocolversion.save()

        story_count = Story.objects.count()
        assert story.author.email == 'test@example.com'
        response = client.post(
            '/stories/%d/transfer' % story.pk,
            data={
                'email': 'other@example.com',
            },
        )
        assert response.status_code == 200
        story.refresh_from_db()
        assert story.author == logged_in_user
        assert Story.objects.count() == story_count

    def test_transfer_other_user_has_no_access_to_model_version(self, client, logged_in_user, other_user, helpers,
                                                                story):
        helpers.add_permission(logged_in_user, 'create_model')
        graph = StoryGraph.objects.filter(story=story).first()
        graph.cachedprotocolversion.visibility = 'public'
        graph.cachedprotocolversion.save()
        version = graph.cachedmodelversions.first()
        version.visibility = 'private'
        version.save()

        story_count = Story.objects.count()
        assert story.author.email == 'test@example.com'
        response = client.post(
            '/stories/%d/transfer' % story.pk,
            data={
                'email': 'other@example.com',
            },
        )
        assert response.status_code == 200
        story.refresh_from_db()
        assert story.author == logged_in_user
        assert Story.objects.count() == story_count


@pytest.mark.django_db
class TestStoryCreateView:
    @pytest.fixture
    def models(self, logged_in_user, helpers):
        models = []
        # want to make sure ids from models, protocols and experiments are unique
        # to avoid being able to assign wrong objects
        for i in range(5):
            models.append(recipes.model.make(author=logged_in_user, id=100 + i))
        return models

    @pytest.fixture
    def experiment_versions(self, logged_in_user, helpers, models):
        # make some models and protocols
        protocols = []
        # make sure ids are unique
        for i in range(3):
            protocols.append(recipes.protocol.make(author=logged_in_user, id=200 + i))
        exp_versions = []

        # add some versions and add experiment versions
        for model in models:
            helpers.add_cached_version(model, visibility='private')
            # for the last protocol add another experiment version
            for protocol in protocols + [protocols[-1]]:
                helpers.add_cached_version(protocol, visibility='public')
                exp_version = recipes.experiment_version.make(
                    status='SUCCESS',
                    experiment__model=model,
                    experiment__model_version=model.repocache.latest_version,
                    experiment__protocol=protocol,
                    experiment__protocol_version=protocol.repocache.latest_version)
                exp_version.mkdir()
                with (exp_version.abs_path / 'result.txt').open('w') as f:
                    f.write('experiment results')

                # add graphs
                exp_version.mkdir()
                shutil.copy(Path(__file__).absolute().parent.joinpath('./test.omex'), exp_version.archive_path)
                exp_versions.append(exp_version)
        return exp_versions

    def test_create_story_page_loads(self, logged_in_user, client, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        response = client.get('/stories/new')
        assert response.status_code == 200

    def test_create_story_no_permission(self, logged_in_user, client):
        remove_perm('entities.create_model', logged_in_user)
        response = client.get('/stories/new')
        assert response.status_code == 403

    def test_create_story_without_text_or_graph(self, logged_in_user, client, helpers):
        story_count = Story.objects.count()
        story_text_count = StoryText.objects.count()
        story_graph_count = StoryGraph.objects.count()

        helpers.add_permission(logged_in_user, 'create_model')
        data = {'title': 'new test story',
                'visibility': 'private',
                'graphvisualizer': 'displayPlotFlot',
                'text-TOTAL_FORMS': '1',
                'text-INITIAL_FORMS': '1',
                'text-MIN_NUM_FORMS': '0',
                'text-MAX_NUM_FORMS': '1000',
                'graph-TOTAL_FORMS': '  1',
                'graph-INITIAL_FORMS': '1',
                'graph-MIN_NUM_FORMS': '0',
                'graph-MAX_NUM_FORMS': '1000',
                'text-0-ORDER': '0',
                'text-0-DELETE': 'true',
                'graph-0-ORDER': '1',
                'graph-0-DELETE': 'true'}

        response = client.post('/stories/new', data=data)
        # Does not add story as no graph & no text
        assert response.status_code == 200
        assert Story.objects.count() == story_count
        assert StoryText.objects.count() == story_text_count
        assert StoryGraph.objects.count() == story_graph_count

    def test_create_story(self, logged_in_user, client, helpers):
        story_count = Story.objects.count()
        story_text_count = StoryText.objects.count()
        story_graph_count = StoryGraph.objects.count()
        helpers.add_permission(logged_in_user, 'create_model')

        data = {'title': 'new test story',
                'visibility': 'private',
                'graphvisualizer': 'displayPlotFlot',
                'text-TOTAL_FORMS': '1',
                'text-INITIAL_FORMS': '1',
                'text-MIN_NUM_FORMS': '0',
                'text-MAX_NUM_FORMS': '1000',
                'graph-TOTAL_FORMS': '	1',
                'graph-INITIAL_FORMS': '1',
                'graph-MIN_NUM_FORMS': '0',
                'graph-MAX_NUM_FORMS': '1000',
                'text-0-description': 'test text',
                'text-0-ORDER': '0',
                'graph-0-ORDER': '1',
                'graph-0-DELETE': 'true'}
        response = client.post('/stories/new', data=data)
        assert response.status_code == 302
        assert response.url == reverse('stories:stories')
        assert Story.objects.count() == story_count + 1
        assert StoryText.objects.count() == story_text_count + 1
        assert StoryGraph.objects.count() == story_graph_count

    def test_create_story_with_same_name(self, logged_in_user, client, helpers, story):
        story_count = Story.objects.count()
        story_text_count = StoryText.objects.count()
        story_graph_count = StoryGraph.objects.count()
        helpers.add_permission(logged_in_user, 'create_model')

        data = {'title': story.title,
                'visibility': 'private',
                'graphvisualizer': 'displayPlotFlot',
                'text-TOTAL_FORMS': '1',
                'text-INITIAL_FORMS': '1',
                'text-MIN_NUM_FORMS': '0',
                'text-MAX_NUM_FORMS': '1000',
                'graph-TOTAL_FORMS': '  1',
                'graph-INITIAL_FORMS': '1',
                'graph-MIN_NUM_FORMS': '0',
                'graph-MAX_NUM_FORMS': '1000',
                'text-0-description': 'test text',
                'text-0-ORDER': '0',
                'graph-0-ORDER': '1',
                'graph-0-DELETE': 'true'}
        response = client.post('/stories/new', data=data)
        assert response.status_code == 200
        assert Story.objects.count() == story_count
        assert StoryText.objects.count() == story_text_count
        assert StoryGraph.objects.count() == story_graph_count

    def test_create_story_with_invalid_graph_model(self, logged_in_user, client, helpers, experiment_versions):
        assert Story.objects.count() == 0
        assert StoryText.objects.count() == 0
        assert StoryGraph.objects.count() == 0
        helpers.add_permission(logged_in_user, 'create_model')

        experiment = experiment_versions[-1].experiment
        experiment = experiment_versions[-1].experiment
        data = {'title': 'new test to check error where form missing graph file',
                'visibility': 'public',
                'graphvisualizer': 'displayPlotFlot',
                'text-TOTAL_FORMS': '1',
                'text-INITIAL_FORMS': '1',
                'text-MIN_NUM_FORMS': '0',
                'text-MAX_NUM_FORMS': '1000',
                'graph-TOTAL_FORMS': '  1',
                'graph-INITIAL_FORMS': '1',
                'graph-MIN_NUM_FORMS': '0',
                'graph-MAX_NUM_FORMS': '1000',
                'text-0-description': 'test text',
                'text-0-ORDER': '0',
                'graph-0-ORDER': '1',
                'graph-0-update': 'True',
                'graph-0-id_models': ['model%s' % experiment.model.pk],
                'graph-0-protocol': '%s' % experiment.protocol.pk,
                'graph-0-graphfiles': ''}

        response = client.post('/stories/new', data=data)
        assert response.status_code == 200
        assert Story.objects.count() == 0
        assert StoryText.objects.count() == 0
        assert StoryGraph.objects.count() == 0

    def test_create_story_with_graph_model(self, logged_in_user, client, helpers, experiment_versions):
        assert Story.objects.count() == 0
        assert StoryText.objects.count() == 0
        assert StoryGraph.objects.count() == 0
        helpers.add_permission(logged_in_user, 'create_model')

        experiment = experiment_versions[-1].experiment
        data = {'title': 'new test',
                'visibility': 'public',
                'graphvisualizer': 'displayPlotFlot',
                'text-TOTAL_FORMS': '1',
                'text-INITIAL_FORMS': '1',
                'text-MIN_NUM_FORMS': '0',
                'text-MAX_NUM_FORMS': '1000',
                'graph-TOTAL_FORMS': '  1',
                'graph-INITIAL_FORMS': '1',
                'graph-MIN_NUM_FORMS': '0',
                'graph-MAX_NUM_FORMS': '1000',
                'text-0-description': 'test text',
                'text-0-ORDER': '0',
                'graph-0-ORDER': '1',
                'graph-0-update': 'True',
                'graph-0-id_models': ['model%s' % experiment.model.pk],
                'graph-0-protocol': '%s' % experiment.protocol.pk,
                'graph-0-graphfiles': 'outputs_Relative_resting_potential_gnuplot_data.csv'}

        response = client.post('/stories/new', data=data)
        assert response.status_code == 302
        assert Story.objects.count() == 1
        assert StoryText.objects.count() == 1
        assert StoryGraph.objects.count() == 1

        assert Story.objects.first().title == data['title']
        assert StoryText.objects.first().story == Story.objects.first()
        assert StoryGraph.objects.first().story == Story.objects.first()
        assert StoryGraph.objects.first().cachedprotocolversion == experiment.protocol.repocache.latest_version
        assert list(StoryGraph.objects.first().cachedmodelversions.all()) == [experiment.model.repocache.latest_version]
        assert StoryGraph.objects.first().graphfilename == data['graph-0-graphfiles']

    def test_create_story_with_graph_modelgroup(self, logged_in_user, client, helpers, models, experiment_versions):
        Story.objects.count() == 0
        StoryText.objects.count() == 0
        StoryGraph.objects.count() == 0
        helpers.add_permission(logged_in_user, 'create_model')

        models = models[1:4]
        modelgroup = recipes.modelgroup.make(models=models, author=logged_in_user)
        experiment = experiment_versions[-1].experiment

        data = {'title': 'new test to check error where form save wrong protocol version',
                'visibility': 'public',
                'graphvisualizer': 'displayPlotFlot',
                'text-TOTAL_FORMS': '1',
                'text-INITIAL_FORMS': '1',
                'text-MIN_NUM_FORMS': '0',
                'text-MAX_NUM_FORMS': '1000',
                'graph-TOTAL_FORMS': '  1',
                'graph-INITIAL_FORMS': '1',
                'graph-MIN_NUM_FORMS': '0',
                'graph-MAX_NUM_FORMS': '1000',
                'text-0-description': 'test text',
                'text-0-ORDER': '0',
                'graph-0-ORDER': '1',
                'graph-0-update': 'True',
                'graph-0-id_models': ['modelgroup%s' % modelgroup.pk],
                'graph-0-protocol': '%s' % experiment.protocol.pk,
                'graph-0-graphfiles': 'outputs_Relative_resting_potential_gnuplot_data.csv'}

        response = client.post('/stories/new', data=data)
        assert response.status_code == 302
        assert Story.objects.count() == 1
        assert StoryText.objects.count() == 1
        assert StoryGraph.objects.count() == 1

        assert Story.objects.first().title == data['title']
        assert StoryText.objects.first().story == Story.objects.first()
        assert StoryGraph.objects.first().story == Story.objects.first()
        assert StoryGraph.objects.first().cachedprotocolversion == experiment.protocol.repocache.latest_version
        assert sorted(StoryGraph.objects.first().cachedmodelversions.all(), key=str) == \
            sorted([m.repocache.latest_version for m in models], key=str)
        assert StoryGraph.objects.first().graphfilename == data['graph-0-graphfiles']

    def test_edit_storygraph_initial(self, logged_in_user, client, helpers, models, experiment_versions):
        story = recipes.story.make(author=logged_in_user, title='story1', id=10001)
        models = models[-2:]
        modelgroup = recipes.modelgroup.make(models=models, author=logged_in_user, id=20001)
        experiment = experiment_versions[-1].experiment

        model_group_mv = [m.repocache.latest_version for m in modelgroup.models.all() if m.repocache.versions.count()]
        storygraph = recipes.story_graph.make(id=30001, author=logged_in_user, story=story, modelgroups=[modelgroup],
                                              cachedprotocolversion=experiment.protocol_version, order=0,
                                              cachedmodelversions=model_group_mv,
                                              grouptoggles=[modelgroup],
                                              graphfilename='outputs_Relative_resting_potential_gnuplot_data.csv')

        data = {'title': 'new test to check error where form save wrong protocol version',
                'visibility': 'public',
                'graphvisualizer': 'displayPlotFlot',
                'text-TOTAL_FORMS': '0',
                'text-INITIAL_FORMS': '0',
                'text-MIN_NUM_FORMS': '0',
                'text-MAX_NUM_FORMS': '1000',
                'graph-TOTAL_FORMS': '  1',
                'graph-INITIAL_FORMS': '1',
                'graph-MIN_NUM_FORMS': '0',
                'graph-MAX_NUM_FORMS': '1000',
                'text-0-description': 'test text',
                'graph-0-ORDER': '0',
                'graph-0-update': 'True',
                'graph-0-id_models': ['modelgroup%s' % modelgroup.pk],
                'graph-0-grouptoggles': [modelgroup.pk],
                'graph-0-protocol': '%s' % experiment.protocol.pk,
                'graph-0-graphfiles': 'outputs_Relative_resting_potential_gnuplot_data.csv'}

        response = client.get('/stories/%s/edit' % story.pk, data=data)
        assert response.context['formsetgraph'].initial == [
            {'number': 0,
             'id_models': ['modelgroup%s' % modelgroup.pk],
             'protocol': experiment.protocol.pk,
             'graphfilename': 'outputs_Relative_resting_potential_gnuplot_data.csv',
             'graphfiles': 'outputs_Relative_resting_potential_gnuplot_data.csv',
             'currentGraph': 'outputs_Relative_resting_potential_gnuplot_data.csv',
             'experimentVersionsUpdate': f'/{experiment.latest_version.pk}',
             'experimentVersions': f'/{experiment.latest_version.pk}',
             'update': False,
             'ORDER': 0,
             'grouptoggles': [modelgroup.pk],
             'pk': 30001,
             'protocol_is_latest': True,
             'all_model_versions_latest': True}
        ]

        # check without modelgroup
        storygraph.modelgroups.clear()
        storygraph.models.set(models)
        storygraph.cachedmodelversions.set([experiment.model_version])
        storygraph.save()
        response = client.get('/stories/%s/edit' % story.pk, data=data)
        assert response.context['formsetgraph'].initial == [
            {'number': 0,
             'id_models': [f'model{m.pk}' for m in models],
             'protocol': experiment.protocol.pk,
             'graphfilename': 'outputs_Relative_resting_potential_gnuplot_data.csv',
             'graphfiles': 'outputs_Relative_resting_potential_gnuplot_data.csv',
             'currentGraph': 'outputs_Relative_resting_potential_gnuplot_data.csv',
             'experimentVersionsUpdate': f'/{experiment.latest_version.pk}',
             'experimentVersions': f'/{experiment.latest_version.pk}',
             'update': False,
             'ORDER': 0,
             'grouptoggles': [modelgroup.pk],
             'pk': 30001,
             'protocol_is_latest': True,
             'all_model_versions_latest': True}
        ]

    def test_edit_story_without_text_or_graph(self, logged_in_user, client):
        story = recipes.story.make(author=logged_in_user, title='story1')
        assert story.title == 'story1'
        story_count = Story.objects.count()
        story_text_count = StoryText.objects.count()
        story_graph_count = StoryGraph.objects.count()

        data = {'title': 'mymodel',
                'visibility': 'private',
                'Graphvisualizer': 'displayPlotFlot',
                'text-TOTAL_FORMS': 0,
                'text-INITIAL_FORMS': 0,
                'text-MIN_NUM_FORMS': 0,
                'text-MAX_NUM_FORMS': 1000,
                'graph-TOTAL_FORMS': 0,
                'graph-INITIAL_FORMS': 0,
                'graph-MIN_NUM_FORMS': 0,
                'graph-MAX_NUM_FORMS': 1000}
        response = client.post('/stories/%d/edit' % story.pk, data=data)
        # Does not add story as no graph & no text
        assert response.status_code == 200
        story.refresh_from_db()
        assert story.title == 'story1'
        assert Story.objects.count() == story_count
        assert StoryText.objects.count() == story_text_count
        assert StoryGraph.objects.count() == story_graph_count

    def test_edit_story_no_permission(self, logged_in_user, other_user, client):
        story = recipes.story.make(author=other_user)
        remove_perm('entities.create_model', logged_in_user)
        response = client.get('/stories/%d/edit' % story.pk)
        assert response.status_code == 403

    def test_edit_story_change_title(self, logged_in_user, client):
        story = recipes.story.make(author=logged_in_user, title='story1', visibility='public',
                                   graphvisualizer='displayPlotHC')
        story_text = recipes.story_text.make(story=story, description='new text')
        assert story.title == 'story1'
        assert story.visibility == 'public'
        assert story.graphvisualizer == 'displayPlotHC'

        story_count = Story.objects.count()
        story_text_count = StoryText.objects.count()
        story_graph_count = StoryGraph.objects.count()

        data = {'title': 'new title',
                'visibility': 'private',
                'graphvisualizer': 'displayPlotFlot',
                'text-TOTAL_FORMS': 1,
                'text-INITIAL_FORMS': 1,
                'text-MIN_NUM_FORMS': 0,
                'text-MAX_NUM_FORMS': 1000,
                'graph-TOTAL_FORMS': 0,
                'graph-INITIAL_FORMS': 0,
                'graph-MIN_NUM_FORMS': 0,
                'graph-MAX_NUM_FORMS': 1000,
                'text-0-description': 'edited text field text',
                'text-0-ORDER': 0}
        response = client.post('/stories/%d/edit' % story.pk, data=data)
        assert response.status_code == 302
        assert response.url == reverse('stories:stories')
        assert Story.objects.count() == story_count
        assert StoryText.objects.count() == story_text_count
        assert StoryGraph.objects.count() == story_graph_count

        story.refresh_from_db()
        story_text.refresh_from_db()
        assert story_text.story == story
        assert story_text.description == 'edited text field text'

        assert story.title == 'new title'
        assert story.visibility == 'private'
        assert story.graphvisualizer == 'displayPlotFlot'

    def test_edit_story_keep_title(self, logged_in_user, client):
        story = recipes.story.make(author=logged_in_user, title='story1', visibility='public',
                                   graphvisualizer='displayPlotHC')
        story_text = recipes.story_text.make(story=story, description='new text')
        assert story.title == 'story1'
        assert story.visibility == 'public'
        assert story.graphvisualizer == 'displayPlotHC'

        story_count = Story.objects.count()
        story_text_count = StoryText.objects.count()
        story_graph_count = StoryGraph.objects.count()

        data = {'title': story.title,
                'visibility': 'private',
                'graphvisualizer': 'displayPlotFlot',
                'text-TOTAL_FORMS': 1,
                'text-INITIAL_FORMS': 1,
                'text-MIN_NUM_FORMS': 0,
                'text-MAX_NUM_FORMS': 1000,
                'graph-TOTAL_FORMS': 0,
                'graph-INITIAL_FORMS': 0,
                'graph-MIN_NUM_FORMS': 0,
                'graph-MAX_NUM_FORMS': 1000,
                'text-0-description': 'edited text field text',
                'text-0-ORDER': 0}
        response = client.post('/stories/%d/edit' % story.pk, data=data)
        assert response.status_code == 302
        assert response.url == reverse('stories:stories')
        assert Story.objects.count() == story_count
        assert StoryText.objects.count() == story_text_count
        assert StoryGraph.objects.count() == story_graph_count

        story.refresh_from_db()
        story_text.refresh_from_db()
        assert story_text.story == story
        assert story_text.description == 'edited text field text'

        assert story.title == 'story1'
        assert story.visibility == 'private'
        assert story.graphvisualizer == 'displayPlotFlot'


@pytest.mark.django_db
class TestStoryFilterModelOrGroupView:
    def test_requires_login(self, client):
        response = client.get('/stories/modelorgroup')
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_get_model_groups(self, logged_in_user, other_user, client, helpers):
        recipes.model.make(author=logged_in_user, name='model-mine')
        recipes.modelgroup.make(author=logged_in_user, title='my-modelgroup')

        model_other = recipes.model.make(author=other_user, name='model-other')
        helpers.add_version(model_other)
        recipes.modelgroup.make(author=other_user, title='other-modelgroup', visibility='private')
        recipes.modelgroup.make(author=other_user, title='public-modelgroup', visibility='public')

        response = client.get('/stories/modelorgroup')
        assert response.status_code == 200
        assert 'model-mine' not in str(response.content)  # has no version
        assert 'my-modelgroup' in str(response.content)
        assert 'public-modelgroup' in str(response.content)
        assert 'model-other' not in str(response.content)
        assert 'other-modelgroup' not in str(response.content)


@pytest.mark.django_db
class TestStoryFilterProtocolView:
    def test_requires_login(self, client):
        model = recipes.model.make()
        cached_model = recipes.cached_model.make(entity=model)
        recipes.cached_model_version.make(entity=cached_model)
        response = client.get('/stories/model%d/protocols' % model.pk)
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_get_protocol_not_visible(self, client, logged_in_user, experiment_with_result):
        experiment = experiment_with_result.experiment
        response = client.get('/stories/model%d/protocols' % experiment.model.pk)
        assert response.status_code == 200
        assert experiment.protocol.name not in str(response.content)

    def test_get_protocol(self, client, logged_in_user, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment
        response = client.get('/stories/model%d/protocols' % experiment.model.pk)
        assert response.status_code == 200
        assert experiment.protocol.name in str(response.content)

    def test_get_protocol_via_modelgroup(self, client, logged_in_user, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment
        modelgroup = recipes.modelgroup.make(author=logged_in_user, models=[experiment.model])
        response = client.get('/stories/modelgroup%d/protocols' % modelgroup.pk)
        assert response.status_code == 200
        assert experiment.protocol.name in str(response.content)

    def test_get_protocol_no_modelid(self, client, logged_in_user, experiment_with_result_public):
        response = client.get('/stories/protocols')
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == '<option value="">--------- protocol</option>'

    def test_get_protocol_via_modelgroup_multile_versions(self, client, logged_in_user, experiment_with_result,
                                                          helpers, other_user):
        # test added to check we don't get the same protocol twice of there are multiple versions
        # (verified that the test fails with the old version of the views)
        experiment = experiment_with_result.experiment
        experiment.protool = recipes.protocol.make(author=logged_in_user, id=200001)
        experiment.protocol_version = helpers.add_cached_version(experiment.protocol, visibility='public')
        experiment.save()

        # add a new model & run the experiment with the same protocol
        model2 = recipes.model.make()
        helpers.add_cached_version(model2, visibility='public')
        version = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=model2,
            experiment__model_version=model2.repocache.latest_version,
            experiment__protocol=experiment.protocol,
            experiment__protocol_version=experiment.protocol.repocache.latest_version,
        )
        version.mkdir()
        with (version.abs_path / 'result.txt').open('w') as f:
            f.write('experiment results')

        # add new protocol version
        old_protocol_version = experiment.protocol_version
        helpers.add_cached_version(experiment.protocol, visibility='public')

        # rerun the experiment with this protocol version & the original experiment
        version = recipes.experiment_version.make(
            status='SUCCESS',
            experiment__model=experiment.model,
            experiment__model_version=experiment.model.repocache.latest_version,
            experiment__protocol=experiment.protocol,
            experiment__protocol_version=experiment.protocol.repocache.latest_version,
        )
        version.mkdir()
        with (version.abs_path / 'result.txt').open('w') as f:
            f.write('experiment results')

        # make sure everything is public for convenience
        for experiment in Experiment.objects.all():
            experiment.model_version.visibility = 'public'
            experiment.protocol_version.visibility = 'public'
            experiment.model_version.save()
            experiment.protocol_version.save()

        modelgroup = recipes.modelgroup.make(author=logged_in_user, models=[experiment.model, model2])

        response = client.get('/stories/modelgroup%d/protocols' % modelgroup.pk)
        assert response.status_code == 200
        # check we do get the protocol
        assert experiment.protocol.name in str(response.content)
        # check we don't get multiple instances of protocol
        response_without_protocol = str(response.content).replace(experiment.protocol.name, '', 1)
        assert experiment.protocol.name not in response_without_protocol

        # Now check that we do not get the protocol if we make it private
        experiment.protocol.author = other_user
        experiment.protocol_version.visibility = 'private'
        experiment.protocol_version.save()
        old_protocol_version.visibility = 'private'
        old_protocol_version.save()
        experiment.save()

        response = client.get('/stories/model%d/protocols' % experiment.model.pk)
        assert response.status_code == 200
        assert experiment.protocol.name not in str(response.content)

        # check that we do get it if we make us a collaborator
        assign_perm('edit_entity', logged_in_user, experiment.protocol)
        response = client.get('/stories/model%d/protocols' % experiment.model.pk)
        assert response.status_code == 200
        assert experiment.protocol.name in str(response.content)

        # Now check that we do not get the protocol if we make the model private
        # make sure modelgroup just has this model
        experiment.model.author = other_user
        assert len(experiment.model.repocache.versions.all()) == 1
        experiment.model_version.visibility = 'private'
        experiment.model_version.save()
        experiment.model.save()
        response = client.get('/stories/model%d/protocols' % experiment.model.pk)
        assert response.status_code == 200
        assert experiment.protocol.name not in str(response.content)

        # check that we do get it if we make us a collaborator
        assign_perm('edit_entity', logged_in_user, experiment.model)
        response = client.get('/stories/model%d/protocols' % experiment.model.pk)
        assert response.status_code == 200
        assert experiment.protocol.name in str(response.content)

        # check protocol doesn't show if no succesful run for latest protocol version
        protocol = ProtocolEntity.objects.get(pk=experiment.protocol.pk)
        helpers.add_cached_version(protocol, visibility='private')
        assert experiment.versions.count() > 0

        experiment.protocol.repocache.latest_version
        response = client.get('/stories/model%d/protocols' % experiment.model.pk)
        assert response.status_code == 200
        assert experiment.protocol.name not in str(response.content)

        # check it works again if we hide that version
        # remove us as collaborator (version was already private)
        remove_perm('edit_entity', logged_in_user, experiment.protocol)
        response = client.get('/stories/model%d/protocols' % experiment.model.pk)
        assert response.status_code == 200
        assert experiment.protocol.name in str(response.content)


@pytest.mark.django_db
class TestStoryFilterExperimentVersions:
    def test_requires_login(self, experiment_with_result, client):
        experiment = experiment_with_result.experiment
        response = client.get('/stories/model%d/%d/experimentversions' % (experiment.model.pk, experiment.protocol.pk))
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_get_graph_not_visible(self, client, logged_in_user, experiment_with_result):
        experiment = experiment_with_result.experiment
        response = client.get('/stories/model%d/%d/experimentversions' %
                              (experiment.model.pk, experiment.protocol.pk))
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == '/'

    def test_get_graph(self, client, logged_in_user, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment
        response = client.get('/stories/model%d/%d/experimentversions' %
                              (experiment.model.pk, experiment.protocol.pk))
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == '/' + str(experiment_with_result_public.pk)

    def test_get_graph_via_modelgroup(self, client, logged_in_user, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment
        modelgroup = recipes.modelgroup.make(author=logged_in_user, models=[experiment.model])
        response = client.get('/stories/modelgroup%d/%d/experimentversions' %
                              (modelgroup.pk, experiment.protocol.pk))
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == '/' + str(experiment_with_result_public.pk)

    def test_get_graph_no_ids(self, client, logged_in_user, experiment_with_result_public):
        response = client.get('/stories/experimentversions')
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == '/'

    def test_get_graph_no_protocol_id(self, client, logged_in_user, experiment_with_result_public):
        model = experiment_with_result_public.experiment.model
        response = client.get('/stories/model%d/experimentversions' % model.pk)
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == '/'


@pytest.mark.django_db
class TesttoryFilterExperimentsNotRunView:
    def test_requires_login(self, experiment_with_result, client):
        experiment = experiment_with_result.experiment
        response = client.get('/stories/model%d/%d/experimentsnotrun' % (experiment.model.pk, experiment.protocol.pk))
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_model_not_run(self, client, logged_in_user, experiment_with_result_public, helpers):
        experiment = experiment_with_result_public.experiment

        # add another model
        new_model = recipes.model.make(author=logged_in_user, name='test model not run')
        helpers.add_version(new_model, visibility='public')

        # create a model group
        modelgroup = recipes.modelgroup.make(author=logged_in_user, models=[experiment.model, new_model])

        response = client.get('/stories/model%d_modelgroup%d_/%d/experimentsnotrun' %
                              (experiment.model.pk, modelgroup.pk, experiment.protocol.pk))
        assert response.status_code == 200
        resp = response.content.decode("utf-8").strip()
        assert experiment.model.name not in resp
        assert new_model.name in resp
        assert 'Run simulation' in resp

    def test_model_running(self, client, logged_in_user, experiment_with_result_public, helpers):
        experiment = experiment_with_result_public.experiment

        # add another model
        new_model = recipes.model.make(author=logged_in_user, name='test model not run')
        helpers.add_version(new_model, visibility='public')

        # create a model group
        modelgroup = recipes.modelgroup.make(author=logged_in_user, models=[experiment.model, new_model])

        recipes.experiment_version.make(
            status='QUEUED',
            experiment__model=new_model,
            experiment__model_version=new_model.repocache.latest_version,
            experiment__protocol=experiment.protocol,
            experiment__protocol_version=experiment.protocol_version,
        )

        response = client.get('/stories/model%d_modelgroup%d_/%d/experimentsnotrun' %
                              (experiment.model.pk, modelgroup.pk, experiment.protocol.pk))
        assert response.status_code == 200
        resp = response.content.decode("utf-8").strip()
        assert experiment.model.name not in resp
        assert new_model.name in resp
        assert 'QUEUED' in resp

    def test_model_new_model_version(self, client, logged_in_user, experiment_with_result_public, helpers):
        experiment = experiment_with_result_public.experiment
        # make existing graph
        graph = recipes.story_graph.make(author=logged_in_user, cachedprotocolversion=experiment.protocol_version,
                                         cachedmodelversions=[experiment.model_version], models=[experiment.model])

        # add new model version
        helpers.add_version(experiment.model, visibility='public')

        response = client.get('/stories/model%d_/%d/experimentsnotrun/%d' %
                              (experiment.model.pk, experiment.protocol.pk, graph.pk))
        assert response.status_code == 200
        resp = response.content.decode("utf-8").strip()
        assert experiment.model.name in resp
        assert 'Compare model version in existing graph with the latest model version' in resp
        assert 'Compare protocol version in existing graph with the latest protocol version' not in resp

    def test_model_new_protocol_version(self, client, logged_in_user, experiment_with_result_public, helpers):
        experiment = experiment_with_result_public.experiment
        # make existing graph
        graph = recipes.story_graph.make(author=logged_in_user, cachedprotocolversion=experiment.protocol_version,
                                         cachedmodelversions=[experiment.model_version], models=[experiment.model])

        # add new protocol version
        helpers.add_version(experiment.protocol, visibility='public')

        response = client.get('/stories/model%d_/%d/experimentsnotrun/%d' %
                              (experiment.model.pk, experiment.protocol.pk, graph.pk))
        assert response.status_code == 200
        resp = response.content.decode("utf-8").strip()
        assert experiment.model.name in resp
        assert 'Compare model version in existing graph with the latest model version' not in resp
        assert 'Compare protocol version in existing graph with the latest protocol version' in resp

    def test_model_new_model_and_protocol_version(self, client, logged_in_user, experiment_with_result_public, helpers):
        experiment = experiment_with_result_public.experiment
        # make existing graph
        graph = recipes.story_graph.make(author=logged_in_user, cachedprotocolversion=experiment.protocol_version,
                                         cachedmodelversions=[experiment.model_version], models=[experiment.model])

        # add new model version
        helpers.add_version(experiment.model, visibility='public')
        # add new protocol version
        helpers.add_version(experiment.protocol, visibility='public')

        response = client.get('/stories/model%d_/%d/experimentsnotrun/%d' %
                              (experiment.model.pk, experiment.protocol.pk, graph.pk))
        assert response.status_code == 200
        resp = response.content.decode("utf-8").strip()
        assert experiment.model.name in resp
        assert 'Compare model version in existing graph with the latest model version' in resp
        assert 'Compare protocol version in existing graph with the latest protocol version' in resp

    def test_no_protocol(self, client, logged_in_admin, experiment_with_result):
        experiment = experiment_with_result.experiment
        response = client.get('/stories/model%d/experimentsnotrun' %
                              (experiment.model.pk))
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == ''

    def test_no_keys(self, client, logged_in_admin):
        response = client.get('/stories/experimentsnotrun')
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == ''


@pytest.mark.django_db
class TestStoryFilterGroupToggles:
    def test_requires_login(self, experiment_with_result, client):
        experiment = experiment_with_result.experiment
        response = client.get(f'/stories/0/model{experiment.model.pk}/{experiment.protocol.pk}/toggles')
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_no_groups(self, logged_in_user, experiment_with_result, client):
        experiment = experiment_with_result.experiment
        response = client.get(f'/stories/0/model{experiment.model.pk}/{experiment.protocol.pk}/toggles')
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == ''

    def test_no_access_to_groups(self, logged_in_user, other_user, experiment_with_result, client):
        experiment = experiment_with_result.experiment
        recipes.modelgroup.make(author=other_user, visibility='private', models=[experiment.model])
        response = client.get(f'/stories/0/model{experiment.model.pk}/{experiment.protocol.pk}/toggles')
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == ''

    def test_access_to_groups(self, logged_in_user, other_user, experiment_with_result_public, client):
        experiment = experiment_with_result_public.experiment
        recipes.modelgroup.make(author=logged_in_user, visibility='public', models=[experiment.model])
        response = client.get(f'/stories/0/model{experiment.model.pk}/{experiment.protocol.pk}/toggles')
        assert response.status_code == 200
        assert 'my model group1' in response.content.decode("utf-8").strip()


@pytest.mark.django_db
class TestStoryFilterGraphView:
    def test_requires_login(self, experiment_with_result, client):
        experiment = experiment_with_result.experiment
        response = client.get('/stories/model%d/%d/graph' % (experiment.model.pk, experiment.protocol.pk))
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_get_graph_not_visible(self, client, logged_in_user, experiment_with_result):
        experiment = experiment_with_result.experiment
        response = client.get('/stories/model%d/%d/graph' %
                              (experiment.model.pk, experiment.protocol.pk))
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == '<option value="">--------- graph</option>'

    def test_get_graph_not_no_files(self, client, logged_in_admin, experiment_with_result_public_no_file):
        experiment = experiment_with_result_public_no_file.experiment
        response = client.get('/stories/model%d/%d/graph' %
                              (experiment.model.pk, experiment.protocol.pk))
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == '<option value="">--------- graph</option>'

    def test_get_graph(self, client, logged_in_user, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment

        response = client.get('/stories/model%d/%d/graph' %
                              (experiment.model.pk, experiment.protocol.pk))
        assert response.status_code == 200
        assert 'outputs_Resting_potential_gnuplot_data.csv' in str(response.content)
        assert 'outputs_Relative_resting_potential_gnuplot_data.csv' in str(response.content)

    def test_get_graph_via_modelgroup(self, client, logged_in_user, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment
        modelgroup = recipes.modelgroup.make(author=logged_in_user, models=[experiment.model])
        response = client.get('/stories/modelgroup%d/%d/graph' % (modelgroup.pk, experiment.protocol.pk))
        assert response.status_code == 200
        assert 'outputs_Resting_potential_gnuplot_data.csv' in str(response.content)
        assert 'outputs_Relative_resting_potential_gnuplot_data.csv' in str(response.content)

    def test_get_graph_no_ids(self, client, logged_in_user, experiment_with_result_public):
        response = client.get('/stories/graph')
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == '<option value="">--------- graph</option>'

    def test_get_graph_no_protocol_id(self, client, logged_in_user, experiment_with_result_public):
        model = experiment_with_result_public.experiment.model
        response = client.get('/stories/model%d/graph' % model.pk)
        assert response.status_code == 200
        assert response.content.decode("utf-8").strip() == '<option value="">--------- graph</option>'


@pytest.mark.django_db
class TestStoryRenderView:
    @pytest.fixture
    def story_for_render_no_parts(self, experiment_with_result_public):
        story = recipes.story.make(author=experiment_with_result_public.author, visibility='public',
                                   title='story for render')
        return story

    def test_render_not_logged_in(self, client, story_for_render_no_parts, other_user):
        story_for_render_no_parts.author = other_user
        story_for_render_no_parts.visibility = 'private'
        story_for_render_no_parts.save()
        response = client.get('/stories/%d' % story_for_render_no_parts.pk)
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_render_no_access(self, client, story_for_render_no_parts, other_user, logged_in_user):
        story_for_render_no_parts.author = other_user
        story_for_render_no_parts.visibility = 'private'
        story_for_render_no_parts.save()
        response = client.get('/stories/%d' % story_for_render_no_parts.pk)
        assert response.status_code == 403, str(response)

    def test_render_story_no_poarts(self, client, story_for_render_no_parts):
        response = client.get('/stories/%d' % story_for_render_no_parts.pk)
        assert response.status_code == 200, str(response)
        assert '<h1>Story: story for render</h1>' in str(response.content)
        assert '<div class="markdowrenderview">' not in str(response.content)
        assert '<div class="entitiesStorygraph"' not in str(response.content)

    def test_render_story_with_text(self, client, story_for_render_no_parts):
        recipes.story_text.make(author=story_for_render_no_parts.author, story=story_for_render_no_parts,
                                description='new text')
        response = client.get('/stories/%d' % story_for_render_no_parts.pk)
        assert response.status_code == 200, str(response)
        assert '<h1>Story: story for render</h1>' in str(response.content)
        assert '<div class="markdowrenderview">' in str(response.content)
        assert 'new text' in str(response.content)
        assert '<div class="entitiesStorygraph"' not in str(response.content)

    def test_render_story_graph(self, client, story_for_render_no_parts, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment
        recipes.story_graph.make(author=story_for_render_no_parts.author, story=story_for_render_no_parts,
                                 cachedprotocolversion=experiment.protocol_version,
                                 cachedmodelversions=[experiment.model_version],
                                 models=[experiment.model],
                                 graphfilename='outputs_RestingPotential.csv')
        response = client.get('/stories/%d' % story_for_render_no_parts.pk)
        assert response.status_code == 200, str(response)
        assert '<h1>Story: story for render</h1>' in str(response.content)
        assert '<div class="markdowrenderview">' not in str(response.content)
        assert '<div class="entitiesStorygraph"' in str(response.content)
        assert 'outputs_RestingPotential.csv' in str(response.content)
        assert '/graph_for_story"' in str(response.content)

    def test_render_story_graph_group_toggles(self, client, story_for_render_no_parts, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment
        modelgroup = recipes.modelgroup.make(visibility='public',
                                             models=[experiment.model])
        recipes.story_graph.make(author=story_for_render_no_parts.author, story=story_for_render_no_parts,
                                 cachedprotocolversion=experiment.protocol_version,
                                 cachedmodelversions=[experiment.model_version],
                                 models=[experiment.model],
                                 grouptoggles=[modelgroup],
                                 graphfilename='outputs_RestingPotential.csv')
        response = client.get('/stories/%d' % story_for_render_no_parts.pk)
        assert response.status_code == 200, str(response)
        assert '<h1>Story: story for render</h1>' in str(response.content)
        assert '<div class="markdowrenderview">' not in str(response.content)
        assert '<div class="entitiesStorygraph"' in str(response.content)
        assert 'outputs_RestingPotential.csv' in str(response.content)
        assert f'/graph_for_story/{modelgroup.pk}"' in str(response.content)

    def test_render_story_multiple_parts(self, client, story_for_render_no_parts, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment
        recipes.story_text.make(author=story_for_render_no_parts.author, story=story_for_render_no_parts,
                                description='new text 1')
        recipes.story_text.make(author=story_for_render_no_parts.author, story=story_for_render_no_parts,
                                description='new text 2')
        recipes.story_graph.make(author=story_for_render_no_parts.author, story=story_for_render_no_parts,
                                 cachedprotocolversion=experiment.protocol_version,
                                 cachedmodelversions=[experiment.model_version],
                                 models=[experiment.model],
                                 graphfilename='outputs_RestingPotential.csv')
        recipes.story_graph.make(author=story_for_render_no_parts.author, story=story_for_render_no_parts,
                                 cachedprotocolversion=experiment.protocol_version,
                                 models=[experiment.model],
                                 cachedmodelversions=[experiment.model_version], graphfilename='outputs_APD90.csv')
        response = client.get('/stories/%d' % story_for_render_no_parts.pk)
        assert response.status_code == 200, str(response)
        assert '<h1>Story: story for render</h1>' in str(response.content)
        assert '<div class="markdowrenderview">' in str(response.content)
        assert 'new text 1' in str(response.content)
        assert 'new text 2' in str(response.content)
        assert '<div class="entitiesStorygraph"' in str(response.content)
        assert 'outputs_APD90.csv' in str(response.content)
