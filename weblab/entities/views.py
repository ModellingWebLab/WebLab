from braces.views import UserFormKwargsMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest, JsonResponse
from django.views import View
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView

from .forms import FileUploadForm, ModelEntityForm, ProtocolEntityForm
from .models import ModelEntity, ProtocolEntity


class ModelEntityCreateView(LoginRequiredMixin, UserFormKwargsMixin, CreateView):
    model = ModelEntity
    form_class = ModelEntityForm
    success_url = '/'


class ProtocolEntityCreateView(LoginRequiredMixin, UserFormKwargsMixin, CreateView):
    model = ProtocolEntity
    form_class = ProtocolEntityForm
    success_url = '/'


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
        kwargs.update({
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


class FileUploadView(View):
    form_class = FileUploadForm

    def post(self, request, *args, **kwargs):
        form = FileUploadForm(self.request.POST, self.request.FILES)
        if form.is_valid():
            data = form.save()
            upload = data.upload
            doc = {
                "files": [
                    {
                        'is_valid': True,
                        'size': upload.size,
                        'name': upload.name,
                        'url': upload.url,
                    }
                ]
            }
            return JsonResponse(doc)

        else:
            print(form.errors)
            return HttpResponseBadRequest()
