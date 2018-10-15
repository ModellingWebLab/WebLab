import mimetypes
import os.path
import shutil
from itertools import groupby

from braces.views import UserFormKwargsMixin
from django.conf import settings
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
from django.utils.text import get_valid_filename
from django.views import View
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView, FormMixin
from django.views.generic.list import ListView
from git import BadName, GitCommandError

from core.visibility import VisibilityMixin, visibility_check
from experiments.models import Experiment

from .forms import (
    EntityChangeVisibilityForm,
    EntityTagVersionForm,
    EntityVersionForm,
    FileUploadForm,
    ModelEntityForm,
    ProtocolEntityForm,
)
from .models import Entity, ModelEntity, ProtocolEntity


class ModelEntityTypeMixin:
    """
    Mixin for including in pages about `ModelEntity` objects
    """
    model = ModelEntity

    def get_context_data(self, **kwargs):
        kwargs.update({
            'type': ModelEntity.entity_type,
            'other_type': ProtocolEntity.entity_type,
        })
        return super().get_context_data(**kwargs)


class ProtocolEntityTypeMixin:
    """
    Mixin for including in pages about `ProtocolEntity` objects
    """
    model = ProtocolEntity

    def get_context_data(self, **kwargs):
        kwargs.update({
            'type': ProtocolEntity.entity_type,
            'other_type': ModelEntity.entity_type,
        })
        return super().get_context_data(**kwargs)


class VersionMixin:
    """
    Mixin for including in pages describing a specific version
    of an `Entity` object
    """

    def get_commit(self):
        if not hasattr(self, '_commit'):
            try:
                self._commit = self.get_object().repo.get_commit(self.kwargs['sha'])
                if not self._commit:
                    raise Http404
            except BadName:
                raise Http404

        return self._commit

    def get_context_data(self, **kwargs):
        entity = self.get_object()
        tags = entity.repo.tag_dict
        commit = self.get_commit()
        kwargs.update(**{
            'version': commit,
            'visibility': entity.get_version_visibility(commit.hexsha),
            'tags': tags.get(commit.hexsha, []),
            'master_filename': commit.master_filename,
        })
        return super().get_context_data(**kwargs)


class ModelEntityCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, ModelEntityTypeMixin,
    UserFormKwargsMixin, CreateView
):
    """
    Create new model entity
    """
    form_class = ModelEntityForm
    permission_required = 'entities.create_model'
    template_name = 'entities/entity_form.html'

    def get_success_url(self):
        return reverse('entities:model_newversion', args=[self.object.pk])


class ProtocolEntityCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, ProtocolEntityTypeMixin,
    UserFormKwargsMixin, CreateView
):
    """
    Create new protocol entity
    """
    form_class = ProtocolEntityForm
    permission_required = 'entities.create_protocol'
    template_name = 'entities/entity_form.html'

    def get_success_url(self):
        return reverse('entities:protocol_newversion', args=[self.object.pk])


class ModelEntityListView(LoginRequiredMixin, ModelEntityTypeMixin, ListView):
    """
    List all user's model entities
    """
    template_name = 'entities/entity_list.html'

    def get_queryset(self):
        return self.model.objects.filter(author=self.request.user)


class ProtocolEntityListView(LoginRequiredMixin, ProtocolEntityTypeMixin, ListView):
    """
    List all user's protocol entities
    """
    template_name = 'entities/entity_list.html'

    def get_queryset(self):
        return self.model.objects.filter(author=self.request.user)


class EntityVersionView(VisibilityMixin, VersionMixin, DetailView):
    """
    View a version of an entity
    """
    context_object_name = 'entity'
    template_name = 'entities/entity_version.html'

    def get_context_data(self, **kwargs):
        entity = self.get_object()
        visibility = entity.get_version_visibility(self.get_commit().hexsha)
        kwargs['form'] = EntityChangeVisibilityForm(initial={
            'visibility': visibility,
        })
        return super().get_context_data(**kwargs)


class ModelEntityVersionView(ModelEntityTypeMixin, EntityVersionView):
    pass


class ProtocolEntityVersionView(ProtocolEntityTypeMixin, EntityVersionView):
    pass


def get_file_type(filename):
    _, ext = os.path.splitext(filename)

    extensions = {
        'cellml': 'CellML',
        'txt': 'TXTPROTOCOL',
        'xml': 'XMLPROTOCOL',
        'zip': 'COMBINE archive',
        'omex': 'COMBINE archive',
    }

    return extensions.get(ext[1:], 'Unknown')


class EntityVersionJsonView(VisibilityMixin, VersionMixin, SingleObjectMixin, View):
    def _file_json(self, blob):
        obj = self.get_object()
        commit = self.get_commit()

        return {
            'id': blob.name,
            'name': blob.name,
            'filetype': get_file_type(blob.name),
            'size': blob.size,
            'created': commit.committed_at,
            'url': reverse(
                'entities:%s_file_download' % obj.entity_type,
                args=[obj.id, commit.hexsha, blob.name]
            ),
        }

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        commit = self.get_commit()

        files = [
            self._file_json(f)
            for f in commit.files
            if f.name not in ['manifest.xml', 'metadata.rdf']
        ]
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
                'url': reverse(
                    'entities:%s_version' % obj.entity_type,
                    args=[obj.id, commit.hexsha]
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


class ModelEntityVersionJsonView(ModelEntityTypeMixin, EntityVersionJsonView):
    pass


class ProtocolEntityVersionJsonView(ProtocolEntityTypeMixin, EntityVersionJsonView):
    pass


class EntityVersionCompareView(VisibilityMixin, VersionMixin, DetailView):
    context_object_name = 'entity'
    template_name = 'entities/entity_version_compare.html'

    def get_context_data(self, **kwargs):
        entity = self.get_object()
        commit = self.get_commit()

        entity_type = entity.entity_type
        other_type = entity.other_type
        experiments = Experiment.objects.filter(**{
            entity_type: entity.pk,
            ('%s_version' % entity_type): commit.hexsha,
        }).select_related(other_type).order_by(other_type, '-created_at')

        experiments = [
            exp for exp in experiments
            if visibility_check(self.request.user, exp)
        ]

        kwargs['comparisons'] = [
            (obj, list(exp))
            for (obj, exp) in groupby(experiments, lambda exp: getattr(exp, other_type))
        ]

        return super().get_context_data(**kwargs)


class ModelEntityVersionCompareView(ModelEntityTypeMixin, EntityVersionCompareView):
    pass


class ProtocolEntityVersionCompareView(ProtocolEntityTypeMixin, EntityVersionCompareView):
    pass


class EntityView(VisibilityMixin, SingleObjectMixin, RedirectView):
    """
    View an entity

    All this does is redirect to the latest version of the entity.
    """
    model = Entity

    def get_redirect_url(self, *args, **kwargs):
        url_name = 'entities:{}_version'.format(kwargs['entity_type'])
        return reverse(url_name, args=[kwargs['pk'], 'latest'])


class EntityTagVersionView(
    LoginRequiredMixin, FormMixin, VersionMixin, DetailView
):
    """Add a new tag to an existing version of an entity."""
    context_object_name = 'entity'
    form_class = EntityTagVersionForm
    model = Entity
    template_name = 'entities/entity_tag_version.html'

    def get_context_data(self, **kwargs):
        entity = self.get_object()
        kwargs['type'] = entity.entity_type
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        """Check the form and possibly add the tag in the repo.

        Called by Django when a form is submitted.
        """
        form = self.get_form()
        entity = self.object = self.get_object()
        if form.is_valid():
            version = self.kwargs['sha']
            tag = form.cleaned_data['tag']
            try:
                entity.repo.tag(tag, ref=version)
            except GitCommandError as e:
                msg = e.stderr.strip().split(':', 1)[1][2:-1]
                form.add_error('tag', msg)
                return self.form_invalid(form)
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self):
        """What page to show when the form was processed OK."""
        entity = self.get_object()
        version = self.kwargs['sha']
        return reverse('entities:%s_version' % entity.entity_type, args=[entity.id, version])


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
        url_name = 'entities:{}s'.format(self.kwargs['entity_type'])
        return reverse(url_name)


class EntityNewVersionView(
    LoginRequiredMixin, PermissionRequiredMixin, FormMixin, DetailView
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
        return initial

    def get_context_data(self, **kwargs):
        entity = self.get_object()
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

        # Delete files from the index
        deletions = request.POST.getlist('delete_filename[]')
        for filename in deletions:
            path = str(entity.repo_abs_path / filename)
            try:
                entity.repo.rm_file(path)
            except GitCommandError as e:
                git_errors.append(e.stderr)

        # Copy files into the index
        additions = request.POST.getlist('filename[]')
        for upload in entity.files.filter(upload__in=additions):
            src = os.path.join(settings.MEDIA_ROOT, upload.upload.name)
            dest = str(entity.repo_abs_path / upload.original_name)
            files_to_delete.add(src)
            shutil.copy(src, dest)
            try:
                entity.repo.add_file(dest)
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
            if request.POST['tag']:
                try:
                    entity.repo.tag(request.POST['tag'])
                except GitCommandError as e:
                    entity.repo.rollback()
                    for f in entity.repo.untracked_files:
                        os.remove(str(entity.repo_abs_path / f))
                    return self.fail_with_git_errors([e.stderr])

            visibility = request.POST['visibility']
            entity.set_version_visibility(commit.hexsha, visibility)
            entity.repocache.add_version(commit.hexsha)

            # Temporary upload files have been safely committed, so can be deleted
            for filename in files_to_delete:
                os.remove(filename)
            return HttpResponseRedirect(
                reverse('entities:%s' % entity.entity_type, args=[entity.id]))
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


class ModelEntityNewVersionView(ModelEntityTypeMixin, EntityNewVersionView):
    """
    Create a new version of a model
    """
    permission_required = 'entities.create_model_version'


class ProtocolEntityNewVersionView(ProtocolEntityTypeMixin, EntityNewVersionView):
    """
    Create a new version of a protocol
    """
    permission_required = 'entities.create_protocol_version'


class VersionListView(VisibilityMixin, DetailView):
    """
    Base class for listing versions of an entity
    """
    context_object_name = 'entity'
    template_name = 'entities/entity_versions.html'

    def get_context_data(self, **kwargs):
        entity = self.get_object()
        tags = entity.repo.tag_dict
        kwargs.update(**{
            'versions': list(
                (tags.get(commit.hexsha), commit)
                for commit in entity.repo.commits
            )
        })
        return super().get_context_data(**kwargs)


class ModelEntityVersionListView(ModelEntityTypeMixin, VersionListView):
    """
    List versions of a model
    """
    pass


class ProtocolEntityVersionListView(ProtocolEntityTypeMixin, VersionListView):
    """
    List versions of a protocol
    """
    pass


class EntityArchiveView(VisibilityMixin, SingleObjectMixin, VersionMixin, View):
    """
    Download a version of an entity as a COMBINE archive
    """
    model = Entity

    def is_visible_to_anonymous(self, obj):
        """
        Allow anonymous access to entity download under certain conditions

        If an Authorization token is provided and it matches a RunningExperiment
        linked to this entity, access is allowed.
        """
        auth_header = self.request.META.get('HTTP_AUTHORIZATION')
        if auth_header and auth_header.startswith('Token'):
            token = auth_header[5:].strip()

            entity_field = 'experiment_version__experiment__%s' % self.kwargs['entity_type']
            from experiments.models import RunningExperiment
            if RunningExperiment.objects.filter(
                id=token,
                **{entity_field: obj.id}
            ).exists():
                return True

        return super().is_visible_to_anonymous(obj)

    def get(self, request, *args, **kwargs):
        entity = self.get_object()
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


class ChangeVisibilityView(UserPassesTestMixin, VersionMixin, DetailView):
    model = Entity

    # Raise a 403 error rather than redirecting to login,
    # if the user doesn't have the correct permissions.
    raise_exception = True

    def test_func(self):
        return self.get_object().is_visibility_editable_by(self.request.user)

    def post(self, request, *args, **kwargs):
        """
        Check the form and possibly set the visibility

        Called by Django when a form is submitted.
        """
        form = EntityChangeVisibilityForm(self.request.POST)
        if form.is_valid():
            obj = self.get_object()
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


class EntityFileDownloadView(VisibilityMixin, VersionMixin, SingleObjectMixin, View):
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


class ModelEntityFileDownloadView(ModelEntityTypeMixin, EntityFileDownloadView):
    pass


class ProtocolEntityFileDownloadView(ProtocolEntityTypeMixin, EntityFileDownloadView):
    pass
