import pytest
from django import forms
from guardian.shortcuts import assign_perm

from entities.forms import EntityCollaboratorForm


@pytest.mark.django_db
class TestEntityCollaboratorFormSet:
    def _form(self, data, entity, **kwargs):
        form = EntityCollaboratorForm(data, entity=entity, **kwargs)
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

    def test_remove_collaborator(self, public_model, model_creator):
        assign_perm('edit_entity', model_creator, public_model)
        form = self._form({'email': model_creator.email, 'DELETE': True}, public_model)
        assert form.is_valid()
        form.remove_collaborator()
        assert not model_creator.has_perm('edit_entity', public_model)
