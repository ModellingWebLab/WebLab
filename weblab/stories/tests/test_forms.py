import pytest
from django import forms
from guardian.shortcuts import assign_perm

from core import recipes
from stories.models import Story, StoryText, StoryGraph
from stories.form import StoryCollaboratorForm, StoryTextForm
from entities.models import ModelGroup


@pytest.mark.django_db
class TestStoryCollaboratorForm:
    def _form(self, data, entity, **kwargs):
        form = StoryCollaboratorForm(data, entity=entity, **kwargs)
        form.fields['DELETE'] = forms.BooleanField(required=False)
        return form

    def test_loads_collaborator_from_email(self, user, public_model):
        form = self._form({}, public_model, initial={'email': user.email})
        assert form.collaborator == user

    def test_stores_entity_object(self, public_model):
        form = self._form({}, public_model)
        assert form.entity == public_model

    def test_get_user_returns_none_if_not_found(self, public_model):
        form = self._form({}, public_model)
        assert form.entity == public_model
        assert form._get_user('nonexistent@example.com') is None

    def test_loads_user_from_email(self, model_creator, public_model):
        form = self._form({'email': model_creator.email, 'DELETE': False}, public_model)
        assert form.is_valid()
        assert form.cleaned_data['user'] == model_creator
        assert form.cleaned_data['email'] == model_creator.email

    def test_raises_validation_error_on_non_existent_email(self, public_model):
        form = self._form({'email': 'nonexistent@example.com'}, public_model)
        assert not form.is_valid()
        assert 'email' in form.errors

    def test_add_collaborator(self, public_model, model_creator):
        form = self._form({'email': model_creator.email, 'DELETE': False}, public_model)
        assert form.is_valid()
        form.add_collaborator()
        assert model_creator.has_perm('edit_entity', public_model)

    def test_cant_add_author_as_collaborator(self, model_creator):
        model = recipes.model.make(author=model_creator)
        form = self._form({'email': model_creator.email, 'DELETE': False}, model)
        assert not form.is_valid()

    def test_remove_collaborator(self, public_model, model_creator):
        assign_perm('edit_entity', model_creator, public_model)
        form = self._form({'email': model_creator.email, 'DELETE': True}, public_model)
        assert form.is_valid()
        form.remove_collaborator()
        assert not model_creator.has_perm('edit_entity', public_model)


@pytest.mark.django_db
class TestStoryTextFormSet:
    def _form(self, data, entity, **kwargs):
        form = StoryTextForm(data, entity=entity, **kwargs)
        return form

    def test_create_storyText(self, story):
        story_text_count = StoryText.objects.count
        form = self._form({}, None)
        form.fields['description'] = 'simple text example'
        story_text = form.save(story)
        assert StoryText.objects.count == story_text_count + 1
        assert story_text.story == story
        assert story_text.description == 'simple text example'

    def test_load_storyText(self, logged_in_user, story):
        story_text = recipes.story_text.make(author=logged_in_user, story=story, description='test loading')
        form = self._form({'description': story_text.description}, story_text)
        assert form.fields['description'] == 'test loading'

    def test_edit_storyText(self, logged_in_user, story):
        story_text_count = StoryText.objects.count
        story_text = recipes.story_text.make(author=logged_in_user, story=story, description='test loading')
        form = self._form({'description': story_text.description}, story_text)
        form.fields['description'] == 'edited story text'
        story_text = form.save(story)
        assert StoryText.objects.count == story_text_count
        assert story_text.story == story
        assert story_text.description == 'edited story text'

    def test_delete_storyText(self, logged_in_user, story):
        story_text_count = StoryText.objects.count
        story_text = recipes.story_text.make(author=logged_in_user, story=story, description='test loading')
        form = self._form({'description': story_text.description}, story_text)
        assert form.fields['description'] == 'test loading'
        assert StoryText.objects.count == story_text_count + 1
        form.delete()
        assert StoryText.objects.count == story_text_count


@pytest.mark.django_db
class TestStoryGraphFormSet:
    ModelGroup.objects.all
    StoryGraph.objects.all()
    pass


@pytest.mark.django_db
class TestStoryForm:
    Story.objects.all()
    pass
