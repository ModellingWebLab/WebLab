import mimetypes
import os.path
import urllib
from zipfile import ZipFile

from braces.views import UserFormKwargsMixin
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
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
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, FormMixin
from django.views.generic.list import ListView

from core.combine import ManifestWriter
from core.visibility import VisibilityMixin

from .forms import DatasetAddFilesForm, DatasetFileUploadForm, DatasetForm
from .models import Dataset


class DatasetCreateView(
    LoginRequiredMixin, PermissionRequiredMixin,
    UserFormKwargsMixin, CreateView
):
    """
    Create new Dataset
    """
    model = Dataset
    template_name = 'datasets/dataset_form.html'
    permission_required = 'datasets.create_dataset'
    form_class = DatasetForm

    def get_success_url(self):
        return reverse('datasets:addfiles', args=[self.object.pk])


class DatasetListView(LoginRequiredMixin, ListView):
    """
    List all user's datasets
    """
    model = Dataset
    template_name = 'datasets/dataset_list.html'

    def get_queryset(self):
        return Dataset.objects.filter(author=self.request.user)


class DatasetView(VisibilityMixin, DetailView):
    """
    View a Dataset

    """
    model = Dataset
    context_object_name = 'dataset'
    template_name = 'datasets/dataset_detail.html'


class DatasetAddFilesView(
    LoginRequiredMixin, FormMixin, DetailView
):
    """
    Add files to a new Dataset.
    """
    context_object_name = 'dataset'
    template_name = 'datasets/dataset_newversion.html'
    form_class = DatasetAddFilesForm
    model = Dataset

    def post(self, request, *args, **kwargs):
        dataset = self.object = self.get_object()

        additions = request.POST.getlist('filename[]')
        if not dataset.file_uploads.filter(upload__in=additions).exists():
            form = self.get_form()
            form.add_error(None, 'No files were added to this dataset')
            return self.form_invalid(form)

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
                if upload.original_name not in archive.namelist():
                    # Avoid duplicates if user changed their mind about a file and replaced it
                    # TODO: Also handling if user changed their mind but did't replace!
                    archive.write(src, upload.original_name)
                    manifest_writer.add_file(upload.original_name)

            # Create a COMBINE manifest in the archive
            import xml.etree.ElementTree as ET
            archive.writestr('manifest.xml', ET.tostring(manifest_writer.xml_doc.getroot()))

        # Temporary upload files have been safely written, so can be deleted
        for upload in dataset.file_uploads.all():
            os.remove(upload.upload.path)
        # Remove records from the DatasetFile table too
        dataset.file_uploads.all().delete()

        # Show the user the dataset
        return HttpResponseRedirect(
            reverse('datasets:detail', args=[dataset.id]))


class DatasetFileUploadView(View):
    """
    Upload files to a dataset
    """
    form_class = DatasetFileUploadForm

    def post(self, request, *args, **kwargs):
        form = DatasetFileUploadForm(self.request.POST, self.request.FILES)
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
    model = Dataset

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
                'parsedOk': False,
                'visibility': dataset.visibility,
                'created': dataset.created_at,
                'name': dataset.name,
                'files': files,
                'numFiles': len(files),
                'download_url': reverse(
                    'datasets:archive', args=[dataset.id]
                ),
            }
        })


class DatasetFileDownloadView(VisibilityMixin, SingleObjectMixin, View):
    """
    Download an individual file from a dataset
    """
    model = Dataset

    def get(self, request, *args, **kwargs):
        filename = self.kwargs['filename']
        dataset = self.get_object()

        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = 'application/octet-stream'

        try:
            with dataset.open_file(filename) as file_:
                response = HttpResponse(content_type=content_type)
                response['Content-Disposition'] = 'attachment; filename=%s' % filename
                response.write(file_.read())
        except KeyError:
            raise Http404

        return response


class DatasetArchiveView(VisibilityMixin, SingleObjectMixin, View):
    """
    Download an archive of the dataset files
    """
    model = Dataset

    def get(self, request, *args, **kwargs):
        dataset = self.get_object()
        path = dataset.archive_path

        if not path.exists():
            raise Http404

        zipfile_name = os.path.join(
            get_valid_filename('%s.zip' % dataset.name)
        )

        with path.open('rb') as archive:
            response = HttpResponse(content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename=%s' % zipfile_name
            response.write(archive.read())

        return response


class DatasetDeleteView(UserPassesTestMixin, DeleteView):
    """
    Delete dataset
    """
    model = Dataset
    # Raise a 403 error rather than redirecting to login,
    # if the user doesn't have delete permissions.
    raise_exception = True

    def test_func(self):
        return self.get_object().is_deletable_by(self.request.user)

    def get_success_url(self, *args, **kwargs):
        return reverse('datasets:list')
