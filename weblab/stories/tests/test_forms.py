import pytest
from django import forms
from guardian.shortcuts import assign_perm

from core import recipes
from stories.models import Story, StoryText, StoryGraph
from stories.forms import StoryCollaboratorForm, StoryTextForm, StoryTextFormSet, StoryGraphForm, StoryGraphFormSet
from entities.models import ModelGroup


#@pytest.mark.django_db
#class TestStoryCollaboratorForm:
#    def _form(self, data, entity, **kwargs):
#        form = StoryCollaboratorForm(data, entity=entity, **kwargs)
#        form.fields['DELETE'] = forms.BooleanField(required=False)
#        return form
#
#    def test_loads_collaborator_from_email(self, user, story):
#        form = self._form({}, story, initial={'email': user.email})
#        assert form.collaborator == user
#
#    def test_stores_entity_object(self, story):
#        form = self._form({}, story)
#        assert form.entity == story
#
#    def test_get_user_returns_none_if_not_found(self, story):
#        form = self._form({}, story)
#        assert form.entity == story
#        assert form._get_user('nonexistent@example.com') is None
#
#    def test_loads_user_from_email(self, logged_in_user, other_user, experiment_with_result):
#        experiment = experiment_with_result.experiment
#        story = recipes.story.make(author=logged_in_user)
#        recipes.story_text.make(author=logged_in_user, story=story)
#        recipes.story_graph.make(author=story.author, story=story, cachedprotocolversion=experiment.protocol_version,
#                                 cachedmodelversions=[experiment.model_version])
#        form = self._form({'email': other_user.email, 'DELETE': False}, story)
#        assert not form.is_valid()
#
#        experiment.protocol_version.visibility = 'public'
#        experiment.protocol_version.save()
#        assert experiment.protocol_version.protocol.is_version_visible_to_user(experiment.protocol_version.sha,
#                                                                               other_user)
#        form = self._form({'email': other_user.email, 'DELETE': False}, story)
#        assert not form.is_valid()
#
#        experiment.model_version.visibility = 'public'
#        experiment.model_version.save()
#        assert experiment.model_version.model.is_version_visible_to_user(experiment.model_version.sha, other_user)
#
#        form = self._form({'email': other_user.email, 'DELETE': False}, story)
#        assert form.is_valid()
#        assert form.cleaned_data['user'] == other_user
#        assert form.cleaned_data['email'] == other_user.email
#
#    def test_raises_validation_error_on_non_existent_email(self, story):
#        form = self._form({'email': 'nonexistent@example.com'}, story)
#        assert not form.is_valid()
#        assert 'email' in form.errors
#
#    def test_add_collaborator(self, logged_in_user, experiment_with_result, other_user):
#        experiment = experiment_with_result.experiment
#        story = recipes.story.make(author=logged_in_user, visibility='private')
#        recipes.story_text.make(author=logged_in_user, story=story)
#        recipes.story_graph.make(author=story.author, story=story, cachedprotocolversion=experiment.protocol_version,
#                                 cachedmodelversions=[experiment.model_version])
#        assert not other_user.has_perm('edit_story', story)
#
#        experiment.protocol_version.visibility = 'public'
#        experiment.model_version.visibility = 'public'
#        experiment.protocol_version.save()
#        experiment.model_version.save()
#
#        form = self._form({'email': other_user.email, 'DELETE': False}, story)
#        assert form.is_valid()
#        form.add_collaborator()
#        assert other_user.has_perm('edit_story', story)
#
#    def test_cant_add_author_as_collaborator(self, story):
#        form = self._form({'email': story.author.email, 'DELETE': False}, story)
#        assert not form.is_valid()
#
#    def test_remove_collaborator(self, experiment_with_result, logged_in_user, other_user):
#        experiment = experiment_with_result.experiment
#        story = recipes.story.make(author=logged_in_user, visibility='private')
#        recipes.story_text.make(author=logged_in_user, story=story)
#        recipes.story_graph.make(author=story.author, story=story, cachedprotocolversion=experiment.protocol_version,
#                                 cachedmodelversions=[experiment.model_version])
#        experiment.protocol_version.visibility = 'public'
#        experiment.model_version.visibility = 'public'
#        experiment.protocol_version.save()
#        experiment.model_version.save()
#
#        assign_perm('edit_story', other_user, story)
#        assert other_user.has_perm('edit_story', story)
#        form = self._form({'email': other_user.email, 'DELETE': True}, story)
#        assert form.is_valid()
#        form.remove_collaborator()
#        assert not other_user.has_perm('edit_story', story)
#
#
#@pytest.mark.django_db
#class TestStoryTextFormSet:
#    def test_create_storyText(self, story):
#        story_text_count = StoryText.objects.count()
#        form = StoryTextForm(user=story.author, data={})
#        assert not form.is_valid()
#        form = StoryTextForm(user=story.author, data={'description': 'simple text example', 'ORDER': '0'})
#        story_text = form.save(story)
#        assert StoryText.objects.count() == story_text_count + 1
#        assert story_text.story == story
#        assert story_text.description == 'simple text example'
#        assert story_text.order == 0
#
#    def test_load_storyText(self, story):
#        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading')
#        form = StoryTextForm(user=story.author, data={'description': story_text.description, 'pk': story_text.pk})
#        assert form.is_valid()
#        assert form.cleaned_data['description'] == 'test loading'
#
#    def test_edit_storyText(self, story):
#        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading', order=12)
#        story_text_count = StoryText.objects.count()
#        form = StoryTextForm(user=story.author, instance=story_text,
#                             data={'description': 'edited story text', 'ORDER': story_text.order, 'pk': story_text.pk})
#        assert form.is_valid()
#        story_text = form.save(story)
#        assert StoryText.objects.count() == story_text_count  # not created an extra one
#        assert story_text.story == story
#        assert story_text.description == 'edited story text'
#
#    def test_delete_storyText(self, story):
#        story_text_count = StoryText.objects.count()
#        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading', order=12)
#        assert StoryText.objects.count() == story_text_count + 1
#        data = {'description': 'edited story text', 'ORDER': story_text.order, 'pk': story_text.pk}
#        form = StoryTextForm(user=story.author, instance=story_text, data=data)
#        form.initial = data
#        assert form.is_valid()
#        story_text = form.delete()
#        assert StoryText.objects.count() == story_text_count
#
#    def test_create_storyText_via_formset(self, story):
#        story_text_count = StoryText.objects.count()
#        form_kwargs = {'user': story.author}
#        post_data = {'text-TOTAL_FORMS': 1, 'text-INITIAL_FORMS': 1, 'text-MIN_NUM_FORMS': 0,
#                     'text-MAX_NUM_FORMS': 1000, 'text-0-ORDER': 0, 'text-0-description': 'new story text item'}
#        formset = StoryTextFormSet(post_data, prefix='text', initial=[{'ORDER': 0}], form_kwargs=form_kwargs)
#        assert formset.is_valid()
#        new_texts = formset.save(story)
#        assert StoryText.objects.count() == story_text_count + 1
#        assert len(new_texts) == 1
#        assert new_texts[0].story == story
#        assert new_texts[0].author == story.author
#        assert new_texts[0].description == 'new story text item'
#        assert new_texts[0].order == 0
#
#    def test_edit_storyText_via_formset(self, story):
#        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading', order=12)
#        story_text_count = StoryText.objects.count()
#        form_kwargs = {'user': story.author}
#        post_data = {'text-TOTAL_FORMS': 1, 'text-INITIAL_FORMS': 1, 'text-MIN_NUM_FORMS': 0,
#                     'text-MAX_NUM_FORMS': 1000, 'text-0-ORDER': 0, 'text-0-description': 'edited descr'}
#        formset = StoryTextFormSet(post_data, prefix='text', initial=[{'ORDER': 0,
#                                   'pk': story_text.pk, 'description': 'edited descr'}], form_kwargs=form_kwargs)
#        assert formset.is_valid()
#        new_texts = formset.save(story)
#        assert StoryText.objects.count() == story_text_count
#        assert len(new_texts) == 1
#        assert new_texts[0].story == story
#        assert new_texts[0].author == story.author
#        assert new_texts[0].description == 'edited descr'
#        assert new_texts[0].order == 0
#
#    def test_delete_storyText_via_formset(self, story):
#        story_text_count = StoryText.objects.count()
#        form_kwargs = {'user': story.author}
#        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading', order=12)
#        assert StoryText.objects.count() == story_text_count + 1
#        post_data = {'text-TOTAL_FORMS': 1, 'text-INITIAL_FORMS': 1, 'text-MIN_NUM_FORMS': 0,
#                     'text-MAX_NUM_FORMS': 1000, 'text-0-ORDER': story_text.order, 'text-0-DELETE': 'true'}
#        formset = StoryTextFormSet(post_data, prefix='text', initial=[{'ORDER': story_text.order, 'DELETE': True,
#                                   'pk': story_text.pk, 'description': 'test loading'}], form_kwargs=form_kwargs)
#        assert StoryText.objects.count() == story_text_count + 1
#        assert formset.is_valid()
#        formset.save(story)
#        assert StoryText.objects.count() == story_text_count



import shutil
from pathlib import Path
@pytest.fixture
def archive_file_path():
    return str(Path(__file__).absolute().parent.joinpath('./test.omex'))

@pytest.mark.django_db
class TestStoryGraphFormSet:
    def test_create_storyGraph(self, experiment_with_result, archive_file_path):
        experiment = experiment_with_result.experiment
        story_graph_count = StoryGraph.objects.count()
        story = recipes.story.make(author=experiment.model_version.model.author)

        # make sure protocol, model & story have same author for conveniance
        experiment.protocol_version.protocol.author = story.author
        experiment.protocol_version.protocol.save()

        experiment_with_result.mkdir()
        shutil.copy(archive_file_path, str(experiment_with_result.archive_path))

#        # Save graph file
#        experiment_with_result.mkdir()
#        with (experiment_with_result.abs_path / 'outputs-default-plots.csv').open('w') as f:
#            f.write('Plot title,File name,Data file name,Line style,First variable id,Optional second variable id,Optional key variable id')
#            f.write('\n')
#            f.write('"Relative APD90",Relative_APD90.eps,outputs_Relative_APD90_gnuplot_data.csv,linespoints,"potassium_test_concentrations","scaled_APD90"')
#            f.write('\n')
#        with (experiment_with_result.abs_path / 'outputs_Relative_APD90_gnuplot_data.csv').open('w') as f:
#            f.write('experiment results') 
#            f.write('2,120.261')
#            f.write('\n')
#            f.write('3,110.783')
#            f.write('\n')


        files = set()
        # find outputs-contents.csv
#        try:
        plots_data_file = experiment_with_result.open_file('outputs-default-plots.csv').read().decode("utf-8")
        plots_data_stream = io.StringIO(plots_data_file)
        for row in csv.DictReader(plots_data_stream):
            files.add(row['Data file name'])
#        except FileNotFoundError:
#            pass  # This experiemnt version has no graphs

        assert False, str(files)

        data = {'ORDER': '0', 'currentGraph': '', 'update': 'True', 'models_or_group': 'model' + str(experiment.model_version.model.pk),
                'protocol': str(experiment.protocol_version.protocol.pk),
                'graphfiles': 'outputs_Relative_APD90_gnuplot_data.csv'}

        form = StoryGraphForm(data=data, user=story.author)
        assert form.is_valid(), str(form.errors) + "\n" + str(StoryGraphFormSet.get_graph_choices(story.author))
        form.delete()  # should do nothing, as no existing story loaded
        assert StoryGraph.objects.count() == story_graph_count

        story_graph = form.save(story)
        assert StoryGraph.objects.count() == story_graph_count + 1
        assert story_graph.story == story
        assert story_graph.order == 0
        assert story_graph.models_or_group == str(experiment.model_version.model)
        assert list(story_graph.cachedmodelversions) == [experiment.model_version]
        assert story_graph.cachedprotocolversion == experiment.protocol_version
        assert story_graph.modelgroup == None

#StoryGraphForm
        pass

    def test_load_storyGraph(self, story):
        pass

    def test_edit_storyGraph(self, story):
        pass

    def test_delete_storyGraph(self, story):
        pass

    def test_create_storyGraph_via_formset(self, story):
        pass

    def test_load_storyGraph_via_formset(self, story):
        pass

    def test_edit_storyGraph_via_formset(self, story):
        pass

    def test_delete_storyGraph_via_formset(self, story):
        pass


#    ModelGroup.objects.all
#    StoryGraph.objects.all()
#    pass


@pytest.mark.django_db
class TestStoryForm:
    Story.objects.all()
    pass   # public / private visibility checks?
