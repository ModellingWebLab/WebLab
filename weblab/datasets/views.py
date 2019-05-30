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

from .models import ExperimentalDataset

from .forms import (
    FileUploadForm,
)

class ExperimentalDatasetMixin:
    """
    Mixin for including in pages about `Entity` objects
    """
    @property
    def model(self):
        return ExperimentalDataset

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs)


class ExperimentalDatasetCreateView(
    LoginRequiredMixin, PermissionRequiredMixin,
    UserFormKwargsMixin, CreateView
):
    """
    Create new ExperimentalDataset
    """
    template_name = 'datasets/dataset_form.html'
    permission_required='datasets.create_dataset'

    @property
    def form_class(self):
        return FormMixin

    def get_success_url(self):
        return reverse('datasets:newversion',
                       args=[self.object.pk])


class ExperimentalDatasetListView(LoginRequiredMixin, ListView, ExperimentalDatasetMixin):
    """
    List all user's datasets
    """
    template_name = 'datasets/dataset_list.html'

    def get_queryset(self):
        return self.model.objects.filter(author=self.request.user)


# class ExperimentalDatasetView(VisibilityMixin, SingleObjectMixin, RedirectView):
#     """
#     View an ExperimentalDataset
#
#     """
#     model = ExperimentalDataset
#
#     def get_redirect_url(self, *args, **kwargs):
#         return reverse('datasets:newversion', args=[kwargs['pk']])
#
#
# class ExperimentalDatasetDeleteView(UserPassesTestMixin, DeleteView):
#     """
#     Delete an ExperimentalDataset
#     """
#     model = ExperimentalDataset
#     # Raise a 403 error rather than redirecting to login,
#     # if the user doesn't have delete permissions.
#     raise_exception = True
#
#     def test_func(self):
#         return self.get_object().is_deletable_by(self.request.user)
#
#     def get_success_url(self, *args, **kwargs):
#         return reverse('datasets:list')
#

class FileUploadView(View):
    """
    Upload files to an dataset
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
