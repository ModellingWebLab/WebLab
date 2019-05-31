import json
import mimetypes
import os.path
import shutil
import subprocess
import urllib
from itertools import groupby
from tempfile import NamedTemporaryFile
from zipfile import ZipFile

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
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView, FormMixin
from django.views.generic.list import ListView
from git import BadName, GitCommandError
from guardian.shortcuts import get_objects_for_user

from core.combine import ManifestWriter
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
    ExperimentalDatasetAddFilesForm,
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
        return reverse('datasets:addfiles', args=[self.object.pk])


class ExperimentalDatasetListView(LoginRequiredMixin, ListView):
    """
    List all user's datasets
    """
    model = ExperimentalDataset
    template_name = 'datasets/dataset_list.html'

    def get_queryset(self):
        return ExperimentalDataset.objects.filter(author=self.request.user)


class ExperimentalDatasetView(VisibilityMixin, DetailView):
    """
    View an ExperimentalDataset

    """
    model = ExperimentalDataset
    context_object_name = 'dataset'
    template_name = 'datasets/dataset_detail.html'


class ExperimentalDatasetAddFilesView(
    LoginRequiredMixin, FormMixin, DetailView
):
    """
    Add files to a new ExperimentalDataset.
    """
    context_object_name = 'dataset'
    template_name = 'datasets/dataset_newversion.html'
    form_class = ExperimentalDatasetAddFilesForm
    model = ExperimentalDataset

    def post(self, request, *args, **kwargs):
        dataset = self.object = self.get_object()

        additions = request.POST.getlist('filename[]')
        if not dataset.file_uploads.filter(upload__in=additions).exists():
            form = self.get_form()
            form.add_error(None, 'No files were added to this dataset')
            return self.form_invalid(form)

        files_to_delete = set()  # Temp files to be removed if successful

        archive_path = dataset.archive_path
        if archive_path.exists():
            form = self.get_form()
            form.add_error(None, 'Changing files in an existing dataset is not supported')
            return self.form_invalid(form)

        # We're only creating datasets so don't need to handle replacing files
        with ZipFile(str(archive_path), mode='w') as archive:
            manifest_writer = ManifestWriter()
            # Copy new files into the archive
            for upload in dataset.file_uploads.filter(upload__in=additions).order_by('-pk'):
                src = upload.upload.path
                files_to_delete.add(src)
                if upload.original_name not in archive.namelist():
                    # Avoid duplicates if user changed their mind about a file and replaced it
                    # TODO: Also handling if user changed their mind but did't replace!
                    archive.write(src, upload.original_name)
                    manifest_writer.add_file(upload.original_name)

            # Create a COMBINE manifest in the archive
            import xml.etree.ElementTree as ET
            archive.writestr('manifest.xml', ET.tostring(manifest_writer.xml_doc.getroot()))

        # Temporary upload files have been safely written, so can be deleted
        for filepath in files_to_delete:
            os.remove(filepath)
        # Remove records from the DatasetFile table too
        dataset.file_uploads.all().delete()

        # Show the user the dataset
        return HttpResponseRedirect(
            reverse('datasets:detail', args=[dataset.id]))


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


class DatasetJsonView(VisibilityMixin, SingleObjectMixin, View):
    """
    Serve up json view of files in a dataset
    """
    model = ExperimentalDataset

    def _file_json(self, archive_file):
        dataset = self.object
        return {
            'id': archive_file.name,
            'author': dataset.author.full_name,
            'created': dataset.created_at,
            'name': archive_file.name,
            'filetype': archive_file.fmt,
            'masterFile': archive_file.is_master,
            'size': archive_file.size,
            'url': reverse(
                'datasets:file_download',
                args=[dataset.id, urllib.parse.quote(archive_file.name)]
            )
        }

    def get(self, request, *args, **kwargs):
        dataset = self.object = self.get_object()
        files = [
            self._file_json(f)
            for f in dataset.files
            if f.name not in ['manifest.xml', 'metadata.rdf']
        ]

        return JsonResponse({
            'version': {
                'id': dataset.id,
                'author': dataset.author.full_name,
                # 'status': version.status,
                'parsedOk': False,
                'visibility': dataset.visibility,
                'created': dataset.created_at,
                'name': dataset.name,
                # 'experimentId': version.experiment.id,
                # 'version': version.id,
                'files': files,
                'numFiles': len(files),
                # 'download_url': reverse(
                #     'datasets:archive', args=[dataset.id]
                # ),
            }
        })


class DatasetFileDownloadView(VisibilityMixin, SingleObjectMixin, View):
    """
    Download an individual file from a dataset
    """
    model = ExperimentalDataset

    def get(self, request, *args, **kwargs):
        filename = self.kwargs['filename']
        dataset = self.get_object()

        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = 'application/octet-stream'

        with dataset.open_file(filename) as file_:
            response = HttpResponse(content_type=content_type)
            response['Content-Disposition'] = 'attachment; filename=%s' % filename
            response.write(file_.read())

        return response
