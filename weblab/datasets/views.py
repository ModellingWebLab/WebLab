import mimetypes
import os.path
import shutil
from itertools import groupby
from zipfile import ZipFile

from braces.views import UserFormKwargsMixin
from django.contrib import messages
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.urls import reverse
from django.views import View
from django.views.generic.detail import DetailView, SingleObjectMixin
from django.views.generic.edit import CreateView, DeleteView, FormMixin
from django.views.generic.list import ListView

from accounts.forms import OwnershipTransferForm
from core.combine import ManifestWriter
from core.visibility import VisibilityMixin
from fitting.models import FittingResult
from repocache.models import ProtocolIoputs

from .forms import (
    DatasetAddFilesForm,
    DatasetColumnMappingForm,
    DatasetFileUploadForm,
    DatasetForm,
    DatasetRenameForm,
)
from .models import Dataset

from entities.views import EditCollaboratorsAbstractView


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
        main_file = request.POST.get('mainEntry')
        with ZipFile(str(archive_path), mode='w') as archive:
            manifest_writer = ManifestWriter()
            # Copy new files into the archive
            for upload in dataset.file_uploads.filter(upload__in=additions).order_by('-pk'):
                src = upload.upload.path
                if upload.original_name not in archive.namelist():
                    # Avoid duplicates if user changed their mind about a file and replaced it
                    # TODO: Also handling if user changed their mind but did't replace!
                    archive.write(src, upload.original_name)
                    manifest_writer.add_file(
                        upload.original_name,
                        is_master=(upload.original_name == main_file),
                    )

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
            reverse('datasets:map_columns', args=[dataset.id]))


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


class DatasetListView(LoginRequiredMixin, ListView):
    """
    List all user's datasets
    """
    model = Dataset
    template_name = 'datasets/dataset_list.html'

    def get_queryset(self):
        return self.model.objects.filter(author=self.request.user)


class DatasetView(VisibilityMixin, DetailView):
    """
    View a Dataset

    """
    model = Dataset
    context_object_name = 'dataset'
    template_name = 'datasets/dataset_detail.html'


class DatasetJsonView(VisibilityMixin, SingleObjectMixin, View):
    """
    Serve up json view of files in a dataset
    """
    model = Dataset

    def get(self, request, *args, **kwargs):
        ns = self.request.resolver_match.namespace
        dataset = self.get_object()
        url_args = [dataset.id]
        return JsonResponse({
            'version': dataset.get_json(ns, url_args)
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

    def check_access_token(self, token):
        """
        Override to allow token based access to dataset archive downloads -
        must match a (fitting) `RunningExperiment` set up against the dataset.
        """
        from experiments.models import RunningExperiment
        return RunningExperiment.objects.filter(
            id=token,
            runnable__fittingresultversion__fittingresult__dataset=self.get_object().id,
        ).exists()

    def get_archive_name(self, dataset):
        return dataset.archive_name

    def get(self, request, *args, **kwargs):
        dataset = self.get_object()
        path = dataset.archive_path

        if not path.exists():
            raise Http404

        zipfile_name = self.get_archive_name(dataset)

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
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':list')


class DatasetTransferView(LoginRequiredMixin, UserPassesTestMixin,
                          FormMixin, DetailView):
    template_name = 'datasets/dataset_transfer_ownership.html'
    context_object_name = 'dataset'
    form_class = OwnershipTransferForm
    model = Dataset

    def _get_object(self):
        if not hasattr(self, 'object'):
            self.object = self.get_object()
        return self.object

    def test_func(self):
        return self._get_object().is_managed_by(self.request.user)

    def post(self, request, *args, **kwargs):
        """Check the form and transfer ownership of the entity.

        Called by Django when a form is submitted.
        """
        form = self.get_form()

        if form.is_valid():
            user = form.cleaned_data['user']
            dataset = self.get_object()
            if self.model.objects.filter(name=dataset.name, author=user).exists():
                form.add_error(None, "User already has a dataset called %s" % dataset.name)
                return self.form_invalid(form)

            old_path = dataset.archive_path
            dataset.author = user
            dataset.save()
            new_path = dataset.archive_path
            dataset.abs_path.mkdir(exist_ok=False, parents=True)
            if old_path.exists():
                shutil.move(str(old_path), str(new_path))
            if old_path.parent.is_dir():
                shutil.rmtree(str(old_path.parent))
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self, *args, **kwargs):
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':list')


class DatasetRenameView(LoginRequiredMixin, UserFormKwargsMixin, UserPassesTestMixin, FormMixin, DetailView):
    template_name = 'datasets/dataset_rename_form.html'
    context_object_name = 'dataset'
    """
    Delete dataset
    """
    model = Dataset
    form_class = DatasetRenameForm

    def _get_object(self):
        if not hasattr(self, 'object'):
            self.object = self.get_object()
        return self.object

    def test_func(self):
        return self._get_object().is_managed_by(self.request.user)

    def post(self, request, *args, **kwargs):
        form = self.get_form()

        if form.is_valid():
            new_name = form.cleaned_data['name']
            dataset = self._get_object()
            old_archive_path = dataset.archive_path
            dataset.name = new_name
            if old_archive_path.exists():
                old_archive_path.rename(dataset.archive_path)
            dataset.save()
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self, *args, **kwargs):
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':detail', args=[self._get_object().id])


class DatasetCompareFittingResultsView(DetailView):
    """
    List fitting results for this dataset, with selection boxes for comparison
    """
    model = Dataset
    template_name = 'datasets/compare_fittings.html'

    def _get_object(self):
        if not hasattr(self, 'object'):
            self.object = self.get_object()
        return self.object

    def get_context_data(self, **kwargs):
        dataset = self._get_object()

        fittings = FittingResult.objects.filter(
            dataset=dataset.pk,
        ).select_related(
            'model',
        ).order_by('model', '-model_version__timestamp', '-protocol_version__timestamp')

        # Ensure all are visible to user
        fittings = [
            fit for fit in fittings
            if fit.is_visible_to_user(self.request.user)
        ]

        # Group fittings by model
        kwargs['comparisons'] = [
            (obj, list(fits))
            for (obj, fits) in groupby(fittings, lambda fit: fit.model)
        ]

        return super().get_context_data(**kwargs)


class DatasetMapColumnsView(UserPassesTestMixin, VisibilityMixin, DetailView):
    model = Dataset
    template_name = 'datasets/map_columns.html'

    # Raise a 403 error rather than redirecting to login,
    # if the user isn't allowed to modify dataset
    raise_exception = True

    def test_func(self):
        return self.get_object().is_editable_by(self.request.user)

    def _get_object(self):
        if not hasattr(self, 'object'):
            self.object = self.get_object()
        return self.object

    def get_forms(self):
        """
        Construct the forms for this view.

        Populates `self.forms` which is a dict mapping protocol version
        to a list of forms for that protocol version. Each protocol version
        has one form per dataset column.

        @return self.forms
        """
        dataset = self._get_object()

        self.forms = {}

        # Group existing mappings by protocol version
        existing_mappings = dataset.column_mappings.all()
        mappings_by_version = {
            version: list(mappings)
            for version, mappings in groupby(existing_mappings, lambda x: x.protocol_version)
        }

        # Full list of protocol versions for this user
        protocol_versions = dataset.protocol.cachedentity.versions.visible_to_user(self.request.user)

        for version in protocol_versions:
            self.forms[version] = []

            # Each form will list all but FLAG ioputs for this protocol version
            ioputs = version.ioputs.exclude(kind=(ProtocolIoputs.FLAG))

            # Index existing mappings for this version by column name
            mappings = {
                mapping.column_name: mapping
                for mapping in mappings_by_version.get(version, [])
            }

            # Create a form for each version/column name combo
            columns = sorted(dataset.column_names)
            for (i, column_name) in enumerate(columns):
                instance = mappings.get(column_name)
                form = DatasetColumnMappingForm(
                    prefix='mapping_%d_%d' % (version.pk, i),
                    data=self.request.POST or None,
                    instance=instance,
                    dataset=dataset,
                    protocol_ioputs=ioputs,
                    initial={
                        'dataset': dataset,
                        'protocol_version': version,
                        'column_name': column_name,
                    },
                )
                self.forms[version].append(form)

        return self.forms

    @property
    def all_forms(self):
        """Iterate through all forms in the view"""
        for forms in self.forms.values():
            yield from forms

    @property
    def all_forms_valid(self):
        """Return true if all forms are valid, false otherwise"""
        return all(form.is_valid() for form in self.all_forms)

    def save_all_forms(self):
        """Save all forms in the view"""
        for form in self.all_forms:
            form.save()

    def get_context_data(self, **kwargs):
        kwargs['forms'] = self.get_forms()
        return super().get_context_data(**kwargs)

    def get_success_url(self):
        """What page to show when the form was processed OK."""
        dataset = self.object
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':map_columns', args=[dataset.id])

    def post(self, request, *args, **kwargs):
        self.object = self._get_object()
        forms = self.get_forms()
        if self.all_forms_valid:
            self.save_all_forms()
            messages.info(self.request, 'Column mappings saved')
            return HttpResponseRedirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(forms=forms))


class DatasetCollaboratorsView(EditCollaboratorsAbstractView):
    template_name = 'datasets/dataset_collaborators_form.html'
    model = Dataset

    def get_context_data(self, **kwargs):
        kwargs['dataset'] = self.object
        return super().get_context_data(**kwargs)

    def get_success_url(self):
        """What page to show when the form was processed OK."""
        dataset = self.object
        ns = self.request.resolver_match.namespace
        return reverse(ns + ':entity_collaborators', args=[dataset.id])