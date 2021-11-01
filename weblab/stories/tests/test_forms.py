import pytest
from django import forms
from guardian.shortcuts import assign_perm

from core import recipes
from stories.models import Story, StoryText, StoryGraph
from stories.forms import StoryCollaboratorForm, StoryTextForm, StoryTextFormSet
from entities.models import ModelGroup


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
                                 cachedmodelversions=[experiment.model_version])
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
                                 cachedmodelversions=[experiment.model_version])
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
                                 cachedmodelversions=[experiment.model_version])
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
        assert not form.is_valid()
        form = StoryTextForm(user=story.author, data={'description': 'simple text example', 'ORDER': '0'})
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
                             data={'description': 'edited story text', 'ORDER': story_text.order, 'pk': story_text.pk})
        assert form.is_valid()
        story_text = form.save(story)
        assert StoryText.objects.count() == story_text_count  # not created an extra one
        assert story_text.story == story
        assert story_text.description == 'edited story text'

    def test_delete_storyText(self, story):
        story_text_count = StoryText.objects.count()
        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading', order=12)
        assert StoryText.objects.count() == story_text_count + 1
        data = {'description': 'edited story text', 'ORDER': story_text.order, 'pk': story_text.pk}
        form = StoryTextForm(user=story.author, instance=story_text, data=data)
        form.initial = data
        assert form.is_valid()
        story_text = form.delete()
        assert StoryText.objects.count() == story_text_count

    def test_create_storyText_via_formset(self, story):
        story_text_count = StoryText.objects.count()
        form_kwargs = {'user': story.author}
        post_data = {'text-TOTAL_FORMS': 1, 'text-INITIAL_FORMS': 1, 'text-MIN_NUM_FORMS': 0,
                     'text-MAX_NUM_FORMS': 1000, 'text-0-ORDER': 0, 'text-0-description': 'new story text item'}
        formset = StoryTextFormSet(post_data, prefix='text', form_kwargs=form_kwargs,
                                   initial=[{'ORDER': 0, 'description': 'new story text item'}])
        assert formset.is_valid()
        new_texts = formset.save(story)
        assert StoryText.objects.count() == story_text_count + 1
        assert len(new_texts) == 1
        assert new_texts[0].story == story
        assert new_texts[0].author == story.author
        assert new_texts[0].description == 'new story text item'
        assert new_texts[0].order == 0

    def test_delete_storyText_via_formset(self, story):
        story_text_count = StoryText.objects.count()
        form_kwargs = {'user': story.author}
        story_text = recipes.story_text.make(author=story.author, story=story, description='test loading', order=12)
        assert StoryText.objects.count() == story_text_count + 1
        post_data = {'text-TOTAL_FORMS': 1, 'text-INITIAL_FORMS': 1, 'text-MIN_NUM_FORMS': 0,
                     'text-MAX_NUM_FORMS': 1000, 'text-0-ORDER': story_text.order, 'text-0-DELETE': 'true'}
        formset = StoryTextFormSet(post_data, prefix='text', initial=[{'ORDER': story_text.order, 'DELETE': 'true',
                                   'pk': story_text.pk}], form_kwargs=form_kwargs)
        assert StoryText.objects.count() == story_text_count + 1
        assert formset.is_valid()
        formset.save(story)
        assert StoryText.objects.count() == story_text_count


@pytest.mark.django_db
class TestStoryGraphFormSet:
    ModelGroup.objects.all
    StoryGraph.objects.all()
    pass


@pytest.mark.django_db
class TestStoryForm:
    Story.objects.all()
    pass   # public / private visibility checks?
