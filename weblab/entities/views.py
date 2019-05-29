import json
import mimetypes
import os.path
import shutil
import subprocess
from itertools import groupby
from tempfile import NamedTemporaryFile

import requests
from braces.views import UserFormKwargsMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.core.urlresolvers import reverse
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.core.exceptions import PermissionDenied
from django.db.models import F, Q
from django.utils.decorators import method_decorator
from django.utils.text import get_valid_filename
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView, FormMixin
from django.views.generic.list import ListView
from git import BadName, GitCommandError
from guardian.shortcuts import get_objects_for_user

from core.filetypes import get_file_type
from core.visibility import (
    Visibility, VisibilityMixin
)
from experiments.models import Experiment, PlannedExperiment
from repocache.exceptions import RepoCacheMiss
from repocache.models import CachedEntityVersion

from .forms import (
    EntityChangeVisibilityForm,
    EntityCollaboratorFormSet,
    EntityTagVersionForm,
    EntityVersionForm,
    FileUploadForm,
    ModelEntityForm,
    ProtocolEntityForm,
)
from .models import Entity, ModelEntity, ProtocolEntity
from .processing import process_check_protocol_callback, record_experiments_to_run


class EntityTypeMixin:
    """
    Mixin for including in pages about `Entity` objects
    """
    @property
    def model(self):
        return next(
            et
            for et in (ModelEntity, ProtocolEntity)
            if et.entity_type == self.kwargs['entity_type']
        )

    def get_context_data(self, **kwargs):
        kwargs.update({
            'type': self.model.entity_type,
            'other_type': self.model.other_type,
        })
        return super().get_context_data(**kwargs)


class EntityVersionMixin(VisibilityMixin):
    """
    Mixin for views describing a specific version of an `Entity` object
    """

    def get_visibility(self):
        """
        Visibility comes from the entity version
        """
        try:
            return self._get_object().get_ref_version_visibility(self.kwargs['sha'])
        except RepoCacheMiss:
            raise Http404

    def get_commit(self):
        """
        Get the git commit applicable to this version

        :return: `entities.repository.Commit` object
        :raise: Http404 if commit not found
        """
        if not hasattr(self, '_commit'):
            try:
                self._commit = self._get_object().repo.get_commit(self.kwargs['sha'])
                if not self._commit:
                    raise Http404
            except BadName:
                raise Http404

        return self._commit

    def _get_object(self):
        if not hasattr(self, 'object'):
            self.object = self.get_object()
        return self.object

    def get_context_data(self, **kwargs):
        entity = self._get_object()
        commit = self.get_commit()
        kwargs.update(**{
            'version': commit,
            'visibility': self.get_visibility(),
            'tags': entity.get_tags(commit.hexsha),
            'master_filename': commit.master_filename,
        })
        return super().get_context_data(**kwargs)


class EntityCollaboratorRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.get_object().is_editable_by(self.request.user)


class EntityCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, EntityTypeMixin,
    UserFormKwargsMixin, CreateView
):
    """
    Create new entity
    """
    template_name = 'entities/entity_form.html'

    @property
    def permission_required(self):
        if self.model is ModelEntity:
            return 'entities.create_model'
        elif self.model is ProtocolEntity:
            return 'entities.create_protocol'

    @property
    def form_class(self):
        if self.model is ModelEntity:
            return ModelEntityForm
        elif self.model is ProtocolEntity:
            return ProtocolEntityForm

    def get_success_url(self):
        return reverse('entities:newversion',
                       args=[self.kwargs['entity_type'], self.object.pk])


class EntityListView(LoginRequiredMixin, EntityTypeMixin, ListView):
    """
    List all user's entities of the given type
    """
    template_name = 'entities/entity_list.html'

    def get_queryset(self):
        return self.model.objects.filter(author=self.request.user)


class EntityVersionView(EntityTypeMixin, EntityVersionMixin, DetailView):
    """
    View a version of an entity
    """
    context_object_name = 'entity'
    template_name = 'entities/entity_version.html'

    def get_context_data(self, **kwargs):
        entity = self._get_object()
        visibility = entity.get_version_visibility(self.get_commit().hexsha)
        kwargs['form'] = EntityChangeVisibilityForm(
            user=self.request.user,
            initial={
                'visibility': visibility,
            })
        return super().get_context_data(**kwargs)


class EntityVersionJsonView(EntityTypeMixin, EntityVersionMixin, SingleObjectMixin, View):
    def _file_json(self, blob):
        obj = self._get_object()
        commit = self.get_commit()

        return {
            'id': blob.name,
            'name': blob.name,
            'filetype': get_file_type(blob.name),
            'size': blob.size,
            'created': commit.committed_at,
            'url': reverse(
                'entities:file_download',
                args=[obj.entity_type, obj.id, commit.hexsha, blob.name]
            ),
        }

    def _planned_experiments(self):
        obj = self._get_object()
        commit = self.get_commit()
        kwargs = {
            obj.entity_type: obj,
            obj.entity_type + '_version': commit.hexsha
        }
        return list(PlannedExperiment.objects.filter(**kwargs).values(
            'model', 'protocol', 'model_version', 'protocol_version'))

    def get(self, request, *args, **kwargs):
        obj = self._get_object()
        commit = self.get_commit()

        files = [
            self._file_json(f)
            for f in commit.files
            if f.name not in ['manifest.xml', 'metadata.rdf']
        ]
        if request.user.has_perm('experiments.create_experiment'):
            planned_experiments = self._planned_experiments()
        else:
            planned_experiments = []
        return JsonResponse({
            'version': {
                'id': commit.hexsha,
                'author': obj.author.full_name,
                'entityId': obj.id,
                'visibility': obj.get_version_visibility(commit.hexsha),
                'created': commit.committed_at,
                'name': obj.name,
                'version': obj.repo.get_name_for_commit(commit.hexsha),
                'files': files,
                'numFiles': len(files),
                'planned_experiments': planned_experiments,
                'url': reverse(
                    'entities:version',
                    args=[obj.entity_type, obj.id, commit.hexsha]
                ),
                'download_url': reverse(
                    'entities:entity_archive',
                    args=[obj.entity_type, obj.id, commit.hexsha]
                ),
                'change_url': reverse(
                    'entities:change_visibility',
                    args=[obj.entity_type, obj.id, commit.hexsha]
                ),
            }
        })


class EntityCompareExperimentsView(EntityTypeMixin, EntityVersionMixin, DetailView):
    context_object_name = 'entity'
    template_name = 'entities/compare_experiments.html'

    def get_context_data(self, **kwargs):
        entity = self._get_object()
        commit = self.get_commit()

        entity_type = entity.entity_type
        other_type = entity.other_type
        experiments = Experiment.objects.filter(**{
            entity_type: entity.pk,
            ('%s_version' % entity_type): commit.hexsha,
        }).select_related(other_type).order_by(other_type, '-created_at')

        experiments = [
            exp for exp in experiments
            if exp.is_visible_to_user(self.request.user)
        ]

        kwargs['comparisons'] = [
            (obj, list(exp))
            for (obj, exp) in groupby(experiments, lambda exp: getattr(exp, other_type))
        ]

        return super().get_context_data(**kwargs)


class EntityComparisonView(EntityTypeMixin, TemplateView):
    template_name = 'entities/compare.html'

    def get_context_data(self, **kwargs):
        valid_versions = []
        for version in self.kwargs['versions'].strip('/').split('/'):
            id, sha = version.split(':')
            try:
                entity = Entity.objects.get(pk=id)
                if entity.is_version_visible_to_user(sha, self.request.user):
                    valid_versions.append(version)
            except (RepoCacheMiss, Entity.DoesNotExist):
                messages.error(
                    self.request,
                    'Some requested entities could not be found '
                    '(or you don\'t have permission to see them)'
                )

        kwargs['entity_versions'] = valid_versions
        return super().get_context_data(**kwargs)


class EntityComparisonJsonView(View):
    """
    Serve up JSON view of multiple entity versions for comparison
    """
    def _file_json(self, entity, commit, blob):
        """
        JSON for a single file in a version of the entity

        :param entity: Entity object
        :param commit: `Commit` object
        :param blob: `git.Blob` object
        """
        return {
            'id': blob.name,
            'name': blob.name,
            'author': entity.author.full_name,
            'created': commit.committed_at,
            'filetype': get_file_type(blob.name),
            'size': blob.size,
            'url': reverse(
                'entities:file_download',
                args=[entity.entity_type, entity.id, commit.hexsha, blob.name]
            ),
        }

    def _version_json(self, entity, commit):
        """
        JSON for a single entity version

        :param entity: Entity object
        :param commit: `Commit` object
        """
        files = [
            self._file_json(entity, commit, f)
            for f in commit.files
            if f.name not in ['manifest.xml', 'metadata.rdf']
        ]
        return {
            'id': commit.hexsha,
            'entityId': entity.id,
            'author': entity.author.full_name,
            'parsedOk': False,
            'visibility': entity.get_version_visibility(commit.hexsha, default=entity.DEFAULT_VISIBILITY),
            'created': commit.committed_at,
            'name': entity.name,
            'version': entity.repo.get_name_for_commit(commit.hexsha),
            'files': files,
            'commitMessage': commit.message,
            'numFiles': len(files),
        }

    def get(self, request, *args, **kwargs):
        json_entities = []
        for version in self.kwargs['versions'].strip('/').split('/'):
            id, sha = version.split(':')
            try:
                entity = Entity.objects.get(pk=id)
                if entity.is_version_visible_to_user(sha, request.user):
                    json_entities.append(
                        self._version_json(entity, entity.repo.get_commit(sha))
                    )
            except (RepoCacheMiss, Entity.DoesNotExist):
                pass

        response = {
            'getEntityInfos': {
                'entities': json_entities
            }
        }

        return JsonResponse(response)


class EntityView(VisibilityMixin, SingleObjectMixin, RedirectView):
    """
    View an entity

    All this does is redirect to the latest version of the entity, if it exists.
    Otherwise it redirects to the 'add version' page.
    """
    model = Entity

    def get_redirect_url(self, *args, **kwargs):
        entity = self.get_object()
        if entity.repocache.versions.exists():
            return reverse('entities:version', args=[kwargs['entity_type'], kwargs['pk'], 'latest'])
        else:
            return reverse('entities:newversion', args=[kwargs['entity_type'], kwargs['pk']])


class EntityTagVersionView(
    LoginRequiredMixin, EntityCollaboratorRequiredMixin, FormMixin, EntityVersionMixin, DetailView
):
    """Add a new tag to an existing version of an entity."""
    context_object_name = 'entity'
    form_class = EntityTagVersionForm
    model = Entity
    template_name = 'entities/entity_tag_version.html'

    def get_context_data(self, **kwargs):
        entity = self._get_object()
        kwargs['type'] = entity.entity_type
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        """Check the form and possibly add the tag in the repo.

        Called by Django when a form is submitted.
        """
        form = self.get_form()
        if form.is_valid():
            entity = self._get_object()
            commit = self.get_commit()
            tag = form.cleaned_data['tag']
            try:
                entity.add_tag(tag, commit.hexsha)
            except GitCommandError as e:
                msg = e.stderr.strip().split(':', 1)[1][2:-1]
                form.add_error('tag', msg)
                return self.form_invalid(form)
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self):
        """What page to show when the form was processed OK."""
        entity = self._get_object()
        version = self.kwargs['sha']
        return reverse('entities:version', args=[entity.entity_type, entity.id, version])


class EntityDeleteView(UserPassesTestMixin, DeleteView):
    """
    Delete an entity
    """
    model = Entity
    # Raise a 403 error rather than redirecting to login,
    # if the user doesn't have delete permissions.
    raise_exception = True

    def test_func(self):
        return self.get_object().is_deletable_by(self.request.user)

    def get_success_url(self, *args, **kwargs):
        return reverse('entities:list', args=[self.kwargs['entity_type']])


class EntityAlterFileView(
        EntityTypeMixin, LoginRequiredMixin, EntityCollaboratorRequiredMixin, SingleObjectMixin, View):
    """
    Create a new version of an entity by changing one file through a REST API call.

    The entity type and id are provided in the URL path.

    The post body should be a JSON object with fields:
    * parent_hexsha: string giving the SHA for the commit expected to be the HEAD,
      to guard against simultaneous edits
    * file_name: name of the file to edit
    * file_contents: the new contents of the file
    * visibility: the visibility string for the new version
    * tag: optional short label for the new version
    * commit_message: commit message for the new version
    * rerun_expts: bool saying whether to re-run experiments involving the parent
      commit using the new version
    """

    RESPONSE_OBJECT = 'updateEntityFile'  # The name of our JSON response object

    def json_error(self, message):
        """Return a JSON error response."""
        return JsonResponse({
            self.RESPONSE_OBJECT: {
                'response': False,
                'responseText': message,
            }
        })

    def post(self, request, *args, **kwargs):
        entity = self.object = self.get_object()
        params = json.loads(request.body.decode())

        # Error checking
        parent = entity.repo.latest_commit
        if parent.hexsha != params.get('parent_hexsha'):
            return self.json_error('someone has saved a newer version since you started editing')
        if params.get('file_name') not in parent.filenames:
            return self.json_error('file name provided does not exist in the parent version')
        for arg in ['file_contents', 'visibility', 'commit_message', 'rerun_expts']:
            if arg not in params:
                return self.json_error('missing required argument ' + arg)

        # Store the file and add to index
        path = str(entity.repo_abs_path / params['file_name'])
        with open(path, 'w') as f:
            f.write(params['file_contents'])
        try:
            entity.repo.add_file(path)
        except GitCommandError as e:
            # Reset index & working tree so resubmission works as expected
            entity.repo.hard_reset()
            return self.json_error('failed to add new file version: ' + e.stderr)

        if not entity.repo.has_changes:
            return self.json_error('new version is identical to parent!')

        # Commit and optionally tag the repo
        commit = entity.repo.commit(params['commit_message'], request.user)
        entity.set_visibility_in_repo(commit, params['visibility'])
        entity.repocache.add_version(commit.hexsha)

        tag = params.get('tag', '')
        if tag:
            try:
                entity.add_tag(tag, commit.hexsha)
            except GitCommandError as e:
                entity.repo.rollback()
                return self.json_error('failed to tag version: ' + e.stderr)

        # Trigger entity analysis & experiment runs, if required
        entity.analyse_new_version(commit)
        if params['rerun_expts']:
            record_experiments_to_run(request.user, entity, commit)

        # Show the user the new version
        return JsonResponse({
            self.RESPONSE_OBJECT: {
                'response': True,
                'url': reverse('entities:version', args=[entity.entity_type, entity.id, commit.hexsha]),
            }
        })


class EntityNewVersionView(
    EntityTypeMixin, LoginRequiredMixin, EntityCollaboratorRequiredMixin, FormMixin, DetailView
):
    """
    Create a new version of an entity.
    """
    context_object_name = 'entity'
    template_name = 'entities/entity_newversion.html'
    form_class = EntityVersionForm

    def get_initial(self):
        initial = super().get_initial()
        delete_file = self.request.GET.get('deletefile')
        if delete_file:
            initial['commit_message'] = 'Delete %s' % delete_file
        initial['visibility'] = self.get_object().visibility
        return initial

    def get_form_kwargs(self):
        """Build the kwargs required to instantiate an EntityVersionForm."""
        kwargs = super().get_form_kwargs()
        kwargs['entity_type'] = self.object.entity_type
        return kwargs

    def get_context_data(self, **kwargs):
        entity = self.object
        latest = entity.repo.latest_commit
        if latest:
            kwargs.update(**{
                'latest_version': latest,
                'master_filename': latest.master_filename,
            })

        kwargs['delete_file'] = self.request.GET.get('deletefile')
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        entity = self.object = self.get_object()

        git_errors = []
        files_to_delete = set()  # Temp files to be removed if successful

        deletions = set(request.POST.getlist('delete_filename[]'))
        additions = request.POST.getlist('filename[]')

        # Copy files into the index
        for upload in entity.files.filter(upload__in=additions).order_by('pk'):
            src = upload.upload.path
            dest = str(entity.repo_abs_path / upload.original_name)
            files_to_delete.add(src)
            if upload.original_name in deletions:
                # This is either (i) replacing an existing file, or (ii) a file the user uploaded
                # then decided they didn't want. In either case, don't remove from the repo.
                deletions.remove(upload.original_name)
                if not os.path.exists(dest):
                    # It's the second case (ii), so don't add the file
                    continue
            shutil.copy(src, dest)
            try:
                entity.repo.add_file(dest)
            except GitCommandError as e:
                git_errors.append(e.stderr)

        # Delete files from the index
        for filename in deletions:
            path = str(entity.repo_abs_path / filename)
            try:
                entity.repo.rm_file(path)
            except GitCommandError as e:
                git_errors.append(e.stderr)

        if git_errors:
            # If there were any errors with adding or deleting files,
            # inform the user and reset the index / working tree
            # (as resubmission of the form will do it all again).
            entity.repo.hard_reset()
            return self.fail_with_git_errors(git_errors)

        main_file = request.POST.get('mainEntry')
        entity.repo.generate_manifest(master_filename=main_file)

        if entity.repo.has_changes:
            # Commit and tag the repo
            commit = entity.repo.commit(request.POST['commit_message'], request.user)

            visibility = request.POST['visibility']
            entity.set_visibility_in_repo(commit, visibility)
            entity.repocache.add_version(commit.hexsha)

            tag = request.POST['tag']
            if tag:
                try:
                    entity.add_tag(tag, commit.hexsha)
                except GitCommandError as e:
                    entity.repo.rollback()
                    return self.fail_with_git_errors([e.stderr])

            # Temporary upload files have been safely committed, so can be deleted
            for filepath in files_to_delete:
                os.remove(filepath)
            # Remove records from the EntityFile table too
            entity.files.all().delete()

            # Trigger entity analysis & experiment runs, if required
            entity.analyse_new_version(commit)
            if request.POST.get('rerun_expts'):
                record_experiments_to_run(request.user, entity, commit)

            # Show the user the new version
            return HttpResponseRedirect(
                reverse('entities:version', args=[entity.entity_type, entity.id, commit.hexsha]))
        else:
            # Nothing changed, so inform the user and do nothing else.
            form = self.get_form()
            form.add_error(None, 'No changes were made for this version')
            return self.form_invalid(form)

    def fail_with_git_errors(self, git_errors):
        form = self.get_form()
        for error in git_errors:
            form.add_error(None, 'Git command error: %s' % error)
        return self.form_invalid(form)


class EntityVersionListView(EntityTypeMixin, VisibilityMixin, DetailView):
    """
    Base class for listing versions of an entity
    """
    context_object_name = 'entity'
    template_name = 'entities/entity_versions.html'

    def get_context_data(self, **kwargs):
        entity = self.object

        versions = entity.cachedentity.versions
        if self.request.user not in entity.viewers:
            versions = versions.filter(~Q(visibility=Visibility.PRIVATE))

        kwargs.update(**{
            'versions': list(
                (list(version.tags.values_list('tag', flat=True)),
                 entity.repo.get_commit(version.sha))
                for version in versions.prefetch_related('tags')
            )
        })
        return super().get_context_data(**kwargs)


class EntityArchiveView(SingleObjectMixin, EntityVersionMixin, View):
    """
    Download a version of an entity as a COMBINE archive
    """
    model = Entity

    def check_access_token(self, token):
        """
        Override to allow token based access to entity archive downloads -
        must match a `RunningExperiment` or `AnalysisTask` object set up against the entity
        """
        from entities.models import AnalysisTask
        from experiments.models import RunningExperiment
        entity_field = 'experiment_version__experiment__%s' % self.kwargs['entity_type']
        self_id = self._get_object().id
        return (RunningExperiment.objects.filter(
            id=token,
            **{entity_field: self_id}
        ).exists() or AnalysisTask.objects.filter(id=token, entity=self_id).exists())

    def get(self, request, *args, **kwargs):
        entity = self._get_object()
        commit = self.get_commit()

        zipfile_name = os.path.join(
            get_valid_filename('%s_%s.zip' % (entity.name, commit.hexsha))
        )

        archive = commit.write_archive()

        response = HttpResponse(content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename=%s' % zipfile_name
        response.write(archive.read())

        return response


class FileUploadView(View):
    """
    Upload files to an entity
    """
    form_class = FileUploadForm

    def post(self, request, *args, **kwargs):
        form = FileUploadForm(self.request.POST, self.request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['upload']
            form.instance.entity_id = self.kwargs['pk']
            form.instance.original_name = uploaded_file.name
            data = form.save()
            upload = data.upload
            doc = {
                "files": [
                    {
                        'is_valid': True,
                        'size': upload.size,
                        'name': uploaded_file.name,
                        'stored_name': upload.name,
                        'url': upload.url,
                    }
                ]
            }
            return JsonResponse(doc)

        else:
            return HttpResponseBadRequest(form.errors)


class ChangeVisibilityView(UserPassesTestMixin, EntityVersionMixin, DetailView):
    model = Entity

    # Raise a 403 error rather than redirecting to login,
    # if the user doesn't have the correct permissions.
    raise_exception = True

    def test_func(self):
        return self._get_object().is_visibility_editable_by(self.request.user)

    def post(self, request, *args, **kwargs):
        """
        Check the form and possibly set the visibility

        Called by Django when a form is submitted.
        """
        form = EntityChangeVisibilityForm(self.request.POST, user=self.request.user)
        if form.is_valid():
            obj = self._get_object()
            sha = self.kwargs['sha']
            obj.set_version_visibility(sha, self.request.POST['visibility'])
            response = {
                'updateVisibility': {
                    'response': True,
                    'responseText': 'successfully updated',
                }
            }
        else:
            response = {
                'notifications': {
                    'errors': ['updating visibility failed']
                }
            }

        return JsonResponse(response)


class EntityFileDownloadView(EntityTypeMixin, EntityVersionMixin, SingleObjectMixin, View):
    """
    Download an individual file from an entity version
    """
    def get(self, request, *args, **kwargs):
        filename = self.kwargs['filename']
        version = self.get_commit()

        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = 'application/octet-stream'

        response = HttpResponse(content_type=content_type)
        response['Content-Disposition'] = 'attachment; filename=%s' % filename
        blob = version.get_blob(filename)
        if blob:
            response.write(blob.data_stream.read())
        else:
            raise Http404

        return response


class EntityCollaboratorsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Entity
    formset_class = EntityCollaboratorFormSet
    template_name = 'entities/entity_collaborators_form.html'
    context_object_name = 'entity'

    def _get_object(self):
        if not hasattr(self, 'object'):
            self.object = self.get_object()
        return self.object

    def test_func(self):
        return self._get_object().is_managed_by(self.request.user)

    def handle_no_permission(self):
        if self.raise_exception or self.request.user.is_authenticated:
            raise PermissionDenied(self.get_permission_denied_message())
        else:
            return super().handle_no_permission()

    def get_formset(self):
        entity = self._get_object()
        initial = [{'email': u.email} for u in entity.collaborators]
        form_kwargs = {'entity': entity}
        if self.request.method == 'POST':
            return self.formset_class(
                self.request.POST,
                initial=initial,
                form_kwargs=form_kwargs)
        else:
            return self.formset_class(initial=initial, form_kwargs=form_kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self._get_object()
        formset = self.get_formset()
        if formset.is_valid():
            formset.save()
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(formset=formset))

    def get_success_url(self):
        """What page to show when the form was processed OK."""
        entity = self.object
        return reverse('entities:entity_collaborators', args=[entity.entity_type, entity.id])

    def get_context_data(self, **kwargs):
        if 'formset' not in kwargs:
            kwargs['formset'] = self.get_formset()
        kwargs['type'] = self.object.entity_type
        return super().get_context_data(**kwargs)


@method_decorator(csrf_exempt, name='dispatch')
class CheckProtocolCallbackView(View):
    def post(self, request, *args, **kwargs):
        result = process_check_protocol_callback(json.loads(request.body.decode()))
        return JsonResponse(result)


class GetProtocolInterfacesJsonView(View):
    """Get the interfaces for the latest versions of all protocols visible to the user.

    Returns a JSON object ``{'interfaces': [{'name': str, 'required': [], 'optional': []}, ...]}``
    where ``name`` contains a ``Protocol.name`` and the ``required`` and ``optional`` arrays list
    the terms in that protocol's interface.
    """
    def get(self, request, *args, **kwargs):
        # Base where clause: don't show private versions
        where = ~Q(visibility='private')
        # If the user is logged in, we also need private versions they have access to:
        # from the user's own protocols and those they have permission for
        user = request.user
        if user.is_authenticated:
            visible_protocols = user.entity_set.filter(
                entity_type='protocol'
            ).union(
                get_objects_for_user(user, 'entities.edit_entity'),
            ).values_list(
                'id', flat=True
            )
            where = where | Q(entity__entity__in=visible_protocols)
        # Ensure we only get protocols
        where = Q(entity__entity__entity_type='protocol') & where
        # Now sort and filter these so we only get the latest version per protocol,
        # then annotate with the extra info we need to reduce total query count
        visible_versions = CachedEntityVersion.objects.filter(
            where,
        ).order_by(
            'entity__id',
            '-timestamp',
            '-pk',
        ).distinct(
            'entity__id',
        ).annotate(
            name=F('entity__entity__name'),
        ).prefetch_related(
            'interface'
        )
        interfaces = [
            {
                'name': version.name,
                'required': [iface.term for iface in version.interface.all() if not iface.optional and iface.term],
                'optional': [iface.term for iface in version.interface.all() if iface.optional],
            }
            for version in visible_versions
        ]

        return JsonResponse({
            'interfaces': interfaces
        })


class EntityDiffView(View):
    def _get_unix_diff(self, file1, file2):
        with NamedTemporaryFile() as tmp1, NamedTemporaryFile() as tmp2:
            tmp1.write(file1.data_stream.read())
            tmp2.write(file2.data_stream.read())
            tmp1.flush()
            tmp2.flush()

            result = {}
            try:
                output = subprocess.run(
                    ['diff', '-a', tmp1.name, tmp2.name],
                    stdout=subprocess.PIPE)
                result['unixDiff'] = output.stdout.decode()
                result['response'] = True
            except subprocess.SubprocessError as e:
                result['responseText'] = "Couldn't compute unix diff (%s)" % e

            return result

    def _get_bives_diff(self, file1, file2):
        post_data = {
            'files': [
                file1.data_stream.read().decode(),
                file2.data_stream.read().decode(),
            ],
            'commands': [
                'compHierarchyJson',
                'reactionsJson',
                'reportHtml',
                'xmlDiff',
            ]
        }

        result = {}
        bives_response = requests.post(settings.BIVES_URL, json=post_data)

        if bives_response.ok:
            bives_json = bives_response.json()

            if 'error' in bives_json:
                result['responseText'] = '\n'.join(bives_json['error'])
            else:
                result['bivesDiff'] = bives_json
                result['response'] = True
        else:
            result['responseText'] = (
                'bives request failed: %d (%s)' %
                (bives_response.status_code, bives_response.content.decode())
            )

        return result

    def get(self, request, *args, **kwargs):
        filename = self.kwargs['filename']

        versions = self.kwargs['versions'].strip('/').split('/')

        diff_type = self.request.GET.get('type', 'unix')
        if diff_type == 'unix':
            task = 'getUnixDiff'
        elif diff_type == 'bives':
            task = 'getBivesDiff'
        else:
            return JsonResponse({'error': 'invalid diff type'})

        files = []
        for version in versions:
            id, sha = version.split(':')
            try:
                entity = Entity.objects.get(pk=id)
                if entity.is_version_visible_to_user(sha, request.user):
                    files.append(entity.repo.get_commit(sha).get_blob(filename))
            except (RepoCacheMiss, Entity.DoesNotExist):
                pass

        if len(files) != 2:
            result = {
                'responseText': 'invalid request'
            }
        elif diff_type == 'unix':
            result = self._get_unix_diff(*files)
        elif diff_type == 'bives':
            result = self._get_bives_diff(*files)

        return JsonResponse({
            task: result
        })
