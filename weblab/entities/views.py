import os.path
import shutil

from braces.views import UserFormKwargsMixin
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
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


class ModelEntityCreateView(LoginRequiredMixin, UserFormKwargsMixin, CreateView):
    model = ModelEntity
    form_class = ModelEntityForm

    def get_success_url(self):
        return reverse('entities:model_newversion', args=[self.object.pk])


class ProtocolEntityCreateView(LoginRequiredMixin, UserFormKwargsMixin, CreateView):
    model = ProtocolEntity
    form_class = ProtocolEntityForm
    success_url = '/'

    def get_success_url(self):
        return reverse('entities:protocol_newversion', args=[self.object.pk])


class ModelEntityListView(LoginRequiredMixin, ListView):
    model = ModelEntity

    def get_queryset(self):
        return self.model.objects.filter(author=self.request.user)


class ProtocolEntityListView(LoginRequiredMixin, ListView):
    model = ProtocolEntity

    def get_queryset(self):
        return self.model.objects.filter(author=self.request.user)


class ModelEntityView(LoginRequiredMixin, DetailView):
    model = ModelEntity
    context_object_name = 'entity'

    def get_context_data(self, **kwargs):
        return super().get_context_data(**{
            'type': 'model',
            'other_type': 'protocol'
        })
        return kwargs


class ProtocolEntityView(LoginRequiredMixin, DetailView):
    model = ProtocolEntity
    context_object_name = 'entity'

    def get_context_data(self, **kwargs):
        return super().get_context_data(**{
            'type': 'protocol',
            'other_type': 'model'
        })


class ModelEntityNewVersionView(LoginRequiredMixin, FormMixin, DetailView):
    model = ModelEntity
    template_name = 'entities/modelentity_newversion.html'
    context_object_name = 'entity'
    form_class = EntityVersionForm

    def get_context_data(self, **kwargs):
        return super().get_context_data(**{
            'type': 'model',
            'other_type': 'protocol'
        })

    def post(self, request, *args, **kwargs):
        entity = self.get_object()
        uploads = entity.entityupload_set.filter(
            upload=request.POST['filename[]']
        )

        # Copy each file into the git repo
        for upload in uploads:
            src = os.path.join(settings.MEDIA_ROOT, upload.upload.name)
            dest = os.path.join(entity.repo_file_path, upload.original_name)
            shutil.move(src, dest)
            entity.add_file_to_repo(dest)

        entity.commit_repo(request.POST['commit_message'])
        entity.tag_repo(request.POST['version'])

        return HttpResponseRedirect('/')


class ProtocolEntityNewVersionView(LoginRequiredMixin, DetailView):
    model = ProtocolEntity
    template_name = 'entities/protocolentity_newversion.html'
    context_object_name = 'entity'

    def get_context_data(self, **kwargs):
        return super().get_context_data(**{
            'type': 'protocol',
            'other_type': 'model'
        })

    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class FileUploadView(View):
    form_class = FileUploadForm

    def post(self, request, *args, **kwargs):
        form = FileUploadForm(self.request.POST, self.request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['upload']
            form.instance.entity_id = self.kwargs['pk']
            form.instance.original_name = uploaded_file
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
            print(form.errors)
            return HttpResponseBadRequest()
