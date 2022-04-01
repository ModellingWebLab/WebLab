import pytest
from django import forms
from guardian.shortcuts import assign_perm

from core import recipes
from entities.forms import EntityChangeVisibilityForm, EntityCollaboratorForm, ModelGroupForm
from entities.models import ModelGroup


@pytest.fixture
def models(user):
    return recipes.model.make(_quantity=2, author=user)


@pytest.fixture
def other_models(other_user):
    return recipes.model.make(_quantity=2, author=other_user)


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
class TestEntityVisibilityForm:
    def test_shows_public_and_private_for_regular_user(self, user):
        form = EntityChangeVisibilityForm(user=user)
        assert form.fields['visibility'].valid_value('public')
        assert form.fields['visibility'].valid_value('private')
        assert not form.fields['visibility'].valid_value('moderated')

    def test_shows_moderated_option_for_moderator(self, moderator):
        form = EntityChangeVisibilityForm(user=moderator)
        assert form.fields['visibility'].valid_value('moderated')


@pytest.mark.django_db
class TestModelGroupForm:
    def test_shows_public_and_private_for_regular_user(self, user):
        form = ModelGroupForm(user=user)
        assert form.fields['visibility'].valid_value('public')
        assert form.fields['visibility'].valid_value('private')
        assert not form.fields['visibility'].valid_value('moderated')

    def test_shows_moderated_option_for_moderator(self, moderator):
        form = ModelGroupForm(user=moderator)
        assert form.fields['visibility'].valid_value('moderated')

    def test_shows_all_and_only_visible_models(self, user, other_user, helpers, models, other_models):
        form = ModelGroupForm(user=user)
        assert [(m.id, m.name) for m in models] == list(form.fields['models'].choices)

        form = ModelGroupForm(user=other_user)
        assert [(m.id, m.name) for m in other_models] == list(form.fields['models'].choices)

        helpers.add_version(models[0], visibility='public')
        assign_perm('edit_entity', other_user, models[1])

        form = ModelGroupForm(user=other_user)
        assert [(m.id, m.name) for m in models + other_models] == [i for i in form.fields['models'].choices]

    def test_fil_create_form(self, user, models):
        form_data = {'title': 'new model group', 'visibility': 'private', 'models': [models[0]], }
        form = ModelGroupForm(user=user, data=form_data)
        assert form.is_valid()

        # test save
        assert len(ModelGroup.objects.all()) == 0
        form.save()
        assert len(ModelGroup.objects.all()) == 1
        assert ModelGroup.objects.all()[0].title == 'new model group'
        assert ModelGroup.objects.all()[0].author == user
        assert list(ModelGroup.objects.all()[0].models.all()) == [models[0]]

        # no tite selected
        form_data = {'title': '', 'visibility': 'private', 'models': [models[0]]}
        form = ModelGroupForm(user=user, data=form_data)
        assert not form.is_valid()

        # no models selected
        form_data = {'title': 'new model group', 'visibility': 'private', 'models': []}
        form = ModelGroupForm(user=user, data=form_data)
        assert not form.is_valid()

        # new title exists
        recipes.modelgroup.make(author=user, models=[models[0]], title='existing model group')
        form_data = {'title': 'existing model group', 'visibility': 'private', 'models': [models[0]]}
        form = ModelGroupForm(user=user, data=form_data)
        assert not form.is_valid()

    def test_edit_show_models(self, user, other_user, models, other_models, public_model):
        modelgroup = recipes.modelgroup.make(author=user, models=[public_model])
        form = ModelGroupForm(user=user, instance=modelgroup)
        assert [(m.id, m.name) for m in models + [public_model]] == list(form.fields['models'].choices)
        assert not form.fields['visibility'].disabled
        form = ModelGroupForm(user=other_user, instance=modelgroup)
        assert [(m.id, m.name) for m in [public_model] + other_models]
        assert form.fields['visibility'].disabled

    def test_moderated_only_for_admin_user(self, user, admin_user, models, public_model):
        form_data = {'title': 'new model group', 'visibility': 'public', 'models': [models[0]], }
        form = ModelGroupForm(user=user, data=form_data)
        assert form.fields['visibility'].choices == [('private', 'Private'), ('public', 'Public')]
        assert not form.is_valid()
        form_data['models'] = [public_model]
        form = ModelGroupForm(user=user, data=form_data)
        assert form.is_valid()

        models = recipes.model.make(_quantity=2, author=admin_user)
        form_data = {'title': 'new model group', 'visibility': 'moderated', 'models': [public_model], }
        form = ModelGroupForm(user=admin_user, data=form_data)
        assert form.fields['visibility'].choices == [('private', 'Private'),
                                                     ('public', 'Public'), ('moderated', 'Moderated')]
        assert not form.is_valid()

        models = recipes.model.make(_quantity=2, author=admin_user)
        form_data = {'title': 'new model group', 'visibility': 'public', 'models': [public_model], }
        form = ModelGroupForm(user=admin_user, data=form_data)
        assert form.fields['visibility'].choices == [('private', 'Private'),
                                                     ('public', 'Public'), ('moderated', 'Moderated')]
        assert form.is_valid()

    def test_fil_edit_form(self, user, models):
        modelgroup = recipes.modelgroup.make(title='new model group', author=user, visibility='private')
        modelgroup.models.set([models[0]])
        form_data = {'title': 'edited model group', 'visibility': 'public', 'models': [models[1]], }
        form = ModelGroupForm(user=user, data=form_data, instance=modelgroup)
        assert not form.is_valid()  # visibility too broad for chosen models
        form_data['visibility'] = 'private'
        form = ModelGroupForm(user=user, data=form_data, instance=modelgroup)
        assert form.is_valid()
        # test save
        assert len(ModelGroup.objects.all()) == 1
        assert ModelGroup.objects.first().title == 'new model group'
        assert ModelGroup.objects.first().author == user
        assert ModelGroup.objects.first().visibility == 'private'
        assert list(ModelGroup.objects.all()[0].models.all()) == [models[0]]
        modelgroup = form.save()
        assert len(ModelGroup.objects.all()) == 1
        assert ModelGroup.objects.first().title == 'edited model group'
        assert ModelGroup.objects.first().author == user
        assert ModelGroup.objects.first().visibility == 'private'
        assert list(ModelGroup.objects.first().models.all()) == [models[1]]

        # own title is fine
        form_data = {'title': modelgroup.title, 'visibility': 'private', 'models': [models[0]], }
        form = ModelGroupForm(user=user, data=form_data, instance=modelgroup)
        assert form.is_valid()
        # test save
        modelgroup = form.save()
        assert len(ModelGroup.objects.all()) == 1
        assert ModelGroup.objects.first().title == 'edited model group'
        assert ModelGroup.objects.first().author == user
        assert ModelGroup.objects.first().visibility == 'private'
        assert list(ModelGroup.objects.first().models.all()) == [models[0]]

        # no tite selected
        form_data = {'title': '', 'visibility': 'private', 'models': [models[0]]}
        form = ModelGroupForm(user=user, data=form_data, instance=modelgroup)
        assert not form.is_valid()
        assert len(ModelGroup.objects.all()) == 1

        # no models selected
        form_data = {'title': 'new model group', 'visibility': 'private', 'models': []}
        form = ModelGroupForm(user=user, data=form_data, instance=modelgroup)
        assert not form.is_valid()
        assert len(ModelGroup.objects.all()) == 1

        # new title exists
        recipes.modelgroup.make(author=user, models=[models[0]], title='existing model group')
        form_data = {'title': 'existing model group', 'visibility': 'private', 'models': [models[0]]}
        form = ModelGroupForm(user=user, data=form_data, instance=modelgroup)
        assert not form.is_valid()
        assert len(ModelGroup.objects.all()) == 2

