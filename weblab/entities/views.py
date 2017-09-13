from django.http import HttpResponseBadRequest, JsonResponse
from django.views import View
from django.views.generic.edit import CreateView

from .forms import FileUploadForm, ModelEntityForm
from .models import ModelEntity


class ModelEntityCreateView(CreateView):
    model = ModelEntity
    form_class = ModelEntityForm


class FileUploadView(View):
    form_class = FileUploadForm

    def post(self, request, *args, **kwargs):
        form = FileUploadForm(self.request.POST, self.request.FILES)
        if form.is_valid():
            upload = form.cleaned_data['uploaded_file']
            doc = {
                "files": [
                    {
                        'is_valid': True,
                        'size': upload.size,
                        'name': upload.name,
                    }
                ]
            }
            return JsonResponse(doc)

        else:
            print(form.errors)
            return HttpResponseBadRequest()
