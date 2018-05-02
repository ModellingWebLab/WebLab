import os.path
import shutil

from braces.views import UserFormKwargsMixin
from django.conf import settings
from django.contrib.auth.mixins import (
    AccessMixin,
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
from git import GitCommandError

from core import visibility

from .forms import (
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

    def get_context_data(self, **kwargs):
        entity = self.get_object()
        tags = entity.repo.tag_dict
        version = self.kwargs['sha']
        commit = entity.repo.get_commit(version)
        kwargs.update(**{
            'version': commit,
            'tags': tags.get(commit, []),
            'master_filename': entity.repo.master_filename(version),
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


class EntityVisibilityMixin(AccessMixin, SingleObjectMixin):
    """
    View mixin implementing visiblity restrictions on entity.

    Public entities can be seen by all.
    Restricted entities can be seen only by logged in users.
    Private entities can be seen only by their owner.

    If an entity is not visible to a logged in user, we generate a 404
    If an entity is not visible to an anonymous visitor, redirect to login page
    """

    def dispatch(self, request, *args, **kwargs):
        # We don't necessarily want 'object not found' to give a 404 response
        # (if the user is anonymous it makes more sense to login-redirect them)
        try:
            obj = self.get_object()
        except Http404:
            obj = None

        if self.request.user.is_authenticated():
            # Logged in user can view all except other people's private stuff
            if not obj or (
                obj.author != self.request.user and
                obj.visibility == visibility.PRIVATE
            ):
                raise Http404
        else:
            # Anonymous user can only see public entities
            if not obj or (obj.visibility != visibility.PUBLIC):
                return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)


class ModelEntityVersionView(
    EntityVisibilityMixin, ModelEntityTypeMixin, VersionMixin, DetailView
):
    """
    View a version of a model
    """
    context_object_name = 'entity'
    template_name = 'entities/entity_version.html'


class ProtocolEntityVersionView(
    EntityVisibilityMixin, ProtocolEntityTypeMixin, VersionMixin, DetailView
):
    """
    View a version of a protocol
    """
    context_object_name = 'entity'
    template_name = 'entities/entity_version.html'


class EntityView(EntityVisibilityMixin, SingleObjectMixin, RedirectView):
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
        import git
        form = self.get_form()
        entity = self.object = self.get_object()
        if form.is_valid():
            version = self.kwargs['sha']
            tag = form.cleaned_data['tag']
            try:
                entity.repo.tag(tag, ref=version)
            except git.exc.GitCommandError as e:
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
                'master_filename': entity.repo.master_filename(),
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
            entity.repo.commit(request.POST['commit_message'], request.user)
            if request.POST['tag']:
                try:
                    entity.repo.tag(request.POST['tag'])
                except GitCommandError as e:
                    entity.repo.rollback()
                    for f in entity.repo.untracked_files:
                        os.remove(str(entity.repo_abs_path / f))
                    return self.fail_with_git_errors([e.stderr])

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


class VersionListView(EntityVisibilityMixin, DetailView):
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
                (tags.get(commit), commit)
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


class EntityArchiveView(EntityVisibilityMixin, SingleObjectMixin, View):
    """
    Download a version of an entity as a COMBINE archive
    """
    model = Entity

    def get(self, request, *args, **kwargs):
        entity = self.get_object()
        ref = self.kwargs['sha']
        commit = entity.repo.get_commit(ref)

        if not commit:
            raise Http404

        zipfile_name = os.path.join(
            get_valid_filename('%s_%s.zip' % (entity.name, commit.hexsha))
        )

        archive = entity.repo.archive(ref)

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
