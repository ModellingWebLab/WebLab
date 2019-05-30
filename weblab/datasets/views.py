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
    ExperimentalDatasetForm,
    FileUploadForm,
    ExperimentalDatasetVersionForm,
)


class ExperimentalDatasetCreateView(
    LoginRequiredMixin, PermissionRequiredMixin,
    UserFormKwargsMixin, CreateView
):
    """
    Create new ExperimentalDataset
    """
    model = ExperimentalDataset
    template_name = 'datasets/dataset_form.html'
    permission_required = 'datasets.create_dataset'
    form_class = ExperimentalDatasetForm

    def get_success_url(self):
#        print(reverse('datasets:newversion'))
        return reverse('datasets:newversion', args=[self.object.pk])


class ExperimentalDatasetListView(LoginRequiredMixin, ListView):
    """
    List all user's datasets
    """
    model = ExperimentalDataset
    template_name = 'datasets/dataset_list.html'

    def get_queryset(self):
        return ExperimentalDataset.objects.filter(author=self.request.user)


class ExperimentalDatasetView(VisibilityMixin, SingleObjectMixin, RedirectView):
    """
    View an ExperimentalDataset

    """
    model = ExperimentalDataset

    def get_redirect_url(self, *args, **kwargs):
        return reverse('datasets:newversion', args=[kwargs['pk']])


class ExperimentalDatasetNewVersionView(
    LoginRequiredMixin, FormMixin, DetailView
):
    """
    Create a new version of an ExperimentalDataset.
    """
    context_object_name = 'ExperimentalDataset'
    template_name = 'dataset/dataset_newversion.html'
    form_class = ExperimentalDatasetVersionForm
    model = ExperimentalDataset

    def get_initial(self):
        initial = super().get_initial()
        return initial

    def get_form_kwargs(self):
        """Build the kwargs required to instantiate an ExperimentalDatasetVersionForm."""
        kwargs = super().get_form_kwargs()
        return kwargs

    def get_context_data(self, **kwargs):
        dataset = self.object = self.get_object()
        return super().get_context_data(**kwargs)

    def post(self, request, *args, **kwargs):
        dataset = self.object = self.get_object()

        # TO DO need to copy files but where ??

        # Copy files into the index
#         for upload in ExperimentalDataset.files.filte.order_by('pk'):
#             src = upload.upload.path
#             dest = str(ExperimentalDataset.repo_abs_path / upload.original_name)
#             shutil.copy(src, dest)
#             try:
# #                ExperimentalDataset.repo.add_file(dest)
#             except GitCommandError as e:
# #                git_errors.append(e.stderr)


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
            form.instance.dataset_id = self.kwargs['pk']
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
