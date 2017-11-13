import os.path
import shutil

from braces.views import UserFormKwargsMixin
from django.conf import settings
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
)
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.views import View
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, FormMixin
from django.views.generic.list import ListView

from .forms import (
    EntityVersionForm,
    FileUploadForm,
    ModelEntityForm,
    ProtocolEntityForm,
)
from .models import ModelEntity, ProtocolEntity


class ModelEntityTypeMixin:
    model = ModelEntity

    def get_context_data(self, **kwargs):
        kwargs.update({
            'type': ModelEntity.entity_type,
            'other_type': ProtocolEntity.entity_type,
        })
        return super().get_context_data(**kwargs)


class ProtocolEntityTypeMixin:
    model = ProtocolEntity

    def get_context_data(self, **kwargs):
        kwargs.update({
            'type': ProtocolEntity.entity_type,
            'other_type': ModelEntity.entity_type,
        })
        return super().get_context_data(**kwargs)


class VersionListMixin:
    def get_context_data(self, **kwargs):
        entity = self.get_object()
        tags = entity.tag_dict
        kwargs.update(**{
            'versions': list(
                (tags.get(commit), commit)
                for commit in entity.commits
            )
        })
        return super().get_context_data(**kwargs)


class VersionMixin:
    def get_context_data(self, **kwargs):
        entity = self.get_object()
        tags = entity.tag_dict
        commit = entity.repo.commit(self.kwargs['sha'])
        kwargs.update(**{
            'version': commit,
            'tag': tags.get(commit),
        })
        return super().get_context_data(**kwargs)


class ModelEntityCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, UserFormKwargsMixin, CreateView
):
    model = ModelEntity
    form_class = ModelEntityForm
    permission_required = 'entities.create_model'

    def get_success_url(self):
        return reverse('entities:model_newversion', args=[self.object.pk])


class ProtocolEntityCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, UserFormKwargsMixin, CreateView
):
    model = ProtocolEntity
    form_class = ProtocolEntityForm
    permission_required = 'entities.create_protocol'

    def get_success_url(self):
        return reverse('entities:protocol_newversion', args=[self.object.pk])


class ModelEntityListView(LoginRequiredMixin, ModelEntityTypeMixin, ListView):
    def get_queryset(self):
        return self.model.objects.filter(author=self.request.user)


class ProtocolEntityListView(LoginRequiredMixin, ProtocolEntityTypeMixin, ListView):
    def get_queryset(self):
        return self.model.objects.filter(author=self.request.user)


class ModelEntityView(LoginRequiredMixin, ModelEntityTypeMixin, VersionListMixin, DetailView):
    context_object_name = 'entity'


class ModelEntityVersionView(LoginRequiredMixin, ModelEntityTypeMixin, VersionMixin, DetailView):
    context_object_name = 'entity'
    template_name = 'entities/modelentity_version.html'


class ProtocolEntityVersionView(
    LoginRequiredMixin, ProtocolEntityTypeMixin, VersionMixin, DetailView
):
    context_object_name = 'entity'
    template_name = 'entities/modelentity_version.html'


class ProtocolEntityView(LoginRequiredMixin, ProtocolEntityTypeMixin, VersionListMixin, DetailView):
    context_object_name = 'entity'


class EntityNewVersionView(
    LoginRequiredMixin, PermissionRequiredMixin, FormMixin, DetailView
):
    context_object_name = 'entity'
    form_class = EntityVersionForm

    def post(self, request, *args, **kwargs):
        entity = self.get_object()
        uploads = entity.files.filter(
            upload=request.POST['filename[]']
        )

        # Copy each file into the git repo
        for upload in uploads:
            src = os.path.join(settings.MEDIA_ROOT, upload.upload.name)
            dest = str(entity.repo_abs_path / upload.original_name)
            shutil.move(src, dest)
            entity.add_file_to_repo(dest)

        entity.commit_repo(request.POST['commit_message'],
                           request.user.full_name,
                           request.user.email)
        entity.tag_repo(request.POST['version'])

        return HttpResponseRedirect(
            reverse('entities:%s' % entity.entity_type, args=[entity.id]))


class ModelEntityNewVersionView(ModelEntityTypeMixin, EntityNewVersionView):
    template_name = 'entities/modelentity_newversion.html'
    permission_required = 'entities.create_model_version'


class ProtocolEntityNewVersionView(ProtocolEntityTypeMixin, EntityNewVersionView):
    template_name = 'entities/protocolentity_newversion.html'
    permission_required = 'entities.create_protocol_version'


class FileUploadView(View):
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
