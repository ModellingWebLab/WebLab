import pytest
import shutil
from pathlib import Path

from django.urls import reverse
from guardian.shortcuts import assign_perm, remove_perm

from core import recipes
from stories.models import Story, StoryText, StoryGraph


@pytest.fixture
def experiment_with_result_public(experiment_with_result):
    experiment = experiment_with_result.experiment
    # make sure protocol / models are visible
    experiment.model_version.visibility = 'public'
    experiment.protocol_version.visibility = 'public'
    experiment.model_version.save()
    experiment.protocol_version.save()

    # add graphs
    experiment_with_result.mkdir()
    shutil.copy(Path(__file__).absolute().parent.joinpath('./test.omex'),
                experiment_with_result.archive_path)

    return experiment_with_result


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
    def test_owner_can_delete(self, logged_in_user, client):
        story = recipes.story.make(author=logged_in_user)

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

    def test_owner_can_view_page(self, logged_in_user, client):
        story = recipes.story.make(author=logged_in_user)
        response = client.get('/stories/%d/collaborators' % story.pk)
        assert response.status_code == 200
        assert 'formset' in response.context

    def test_superuser_can_view_page(self, logged_in_admin, client):
        story = recipes.story.make(visibility='private')
        response = client.get('/stories/%d/collaborators' % story.pk)
        assert response.status_code == 200
        assert 'formset' in response.context

    def test_loads_existing_collaborators(self, logged_in_user, other_user, client):
        story = recipes.story.make(author=logged_in_user)
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

    def test_add_non_existent_user_as_editor(self, logged_in_user, client):
        story = recipes.story.make(author=logged_in_user)
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

    def test_remove_editor(self, logged_in_user, other_user, helpers, client):
        story = recipes.story.make(author=logged_in_user)
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

    def test_transfer_invalid_user(self, client, logged_in_user, other_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')

        story = recipes.story.make(author=logged_in_user)

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

    def test_transfer_other_user_has_same_named_entity(self, client, logged_in_user, other_user, helpers):
        helpers.add_permission(logged_in_user, 'create_model')
        story = recipes.story.make(author=logged_in_user)

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


@pytest.mark.django_db
class TestStoryCreateView:
    def test_create_story_without_text_or_graph(self, logged_in_user, client, helpers):
        story_count = Story.objects.count()
        story_text_count = StoryText.objects.count()
        story_graph_count = StoryGraph.objects.count()

        helpers.add_permission(logged_in_user, 'create_model')
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
        response = client.post('/stories/new', data=data)
        # Does not add story as no graph & no text
        assert response.status_code == 200
        assert Story.objects.count() == story_count
        assert StoryText.objects.count() == story_text_count
        assert StoryGraph.objects.count() == story_graph_count

    def test_create_story_no_permission(self, logged_in_user, client, helpers):
        remove_perm('entities.create_model', logged_in_user)
        response = client.get('/stories/new')
        assert response.status_code == 403

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

    def test_create_story_with_same_name(self, logged_in_user, client, helpers):
        story = recipes.story.make(author=logged_in_user)
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


@pytest.mark.django_db
class TestStoryEditView:
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

    def test_get_model_groups(self, logged_in_user, other_user, client):
        recipes.model.make(author=logged_in_user, name='model-mine')
        recipes.modelgroup.make(author=logged_in_user, title='my-modelgroup')

        recipes.model.make(author=other_user, name='model-other')
        recipes.modelgroup.make(author=other_user, title='other-modelgroup', visibility='private')
        recipes.modelgroup.make(author=other_user, title='public-modelgroup', visibility='public')

        response = client.get('/stories/modelorgroup')
        assert response.status_code == 200
        assert 'model-mine' in str(response.content)
        assert 'my-modelgroup' in str(response.content)
        assert 'public-modelgroup' in str(response.content)
        assert 'model-other' not in str(response.content)
        assert 'other-modelgroup' not in str(response.content)


@pytest.mark.django_db
class TestStoryFilterProtocolView:
    def test_requires_login(self, client):
        model = recipes.model.make()
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


@pytest.mark.django_db
class TestStoryFilterGraphView:
    def test_requires_login(self, experiment_with_result, client):
        experiment = experiment_with_result.experiment
        response = client.get('/stories/model%d/%d/graph' % (experiment.model.pk, experiment.protocol.pk))
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_get_graph_not_visible(self, client, logged_in_user, experiment_with_result):
        experiment = experiment_with_result.experiment
        response = client.get('/stories/model%d/%d/graph' % (experiment.model.pk, experiment.protocol.pk))
        assert response.status_code == 200
        assert response.content.decode("utf-8").replace('\n', '') == '<option value="">--------- graph</option>'

    def test_get_graph(self, client, logged_in_user, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment
        response = client.get('/stories/model%d/%d/graph' % (experiment.model.pk, experiment.protocol.pk))
        assert response.status_code == 200
        assert 'outputs_Resting_potential_gnuplot_data.csv' in str(response.content)
        assert 'outputs_Relative_resting_potential_gnuplot_data.csv' in str(response.content)

    def test_get_protocol_via_modelgroup(self, client, logged_in_user, experiment_with_result_public):
        experiment = experiment_with_result_public.experiment
        modelgroup = recipes.modelgroup.make(author=logged_in_user, models=[experiment.model])
        response = client.get('/stories/modelgroup%d/%d/graph' % (modelgroup.pk, experiment.protocol.pk))
        assert response.status_code == 200
        assert 'outputs_Resting_potential_gnuplot_data.csv' in str(response.content)
        assert 'outputs_Relative_resting_potential_gnuplot_data.csv' in str(response.content)


@pytest.mark.django_db
class TestStoryRenderView:
    pass
