import zipfile

from django import forms
from django.core.exceptions import ValidationError

from .models import ExperimentVersion
from .processing import ChasteProcessingStatus


class ExperimentCallbackForm(forms.Form):
    signature = forms.CharField()
    returntype = forms.CharField(required=False)
    returnmsg = forms.CharField(required=False)
    taskid = forms.CharField(required=False)
    experiment = forms.FileField(required=False)

    def clean_signature(self):
        signature = self.cleaned_data['signature']

        try:
            self.version = ExperimentVersion.objects.get(id=signature)
        except ExperimentVersion.DoesNotExist:
            raise ValidationError('invalid signature')

        return signature

    def clean_experiment(self):
        if self.cleaned_data['experiment']:
            try:
                self.zipfile = zipfile.ZipFile(
                    self.cleaned_data['experiment'],
                    'r',
                    zipfile.ZIP_DEFLATED
                )
            except zipfile.BadZipFile as e:
                raise ValidationError('error reading archive: %s' % e)

    def clean(self):
        if hasattr(self, 'version'):
            task_id = self.cleaned_data.get('taskid')
            if task_id:
                self.version.task_id = task_id

            status = self.cleaned_data.get('returntype', ChasteProcessingStatus.SUCCESS)
            self.version.status = ChasteProcessingStatus.get_model_status(status)

            self.version.return_text = self.cleaned_data.get('returnmsg') or 'finished'
            if self.version.is_running:
                self.version.return_text = 'running'
            self.version.save()

    def extract_archive(self):
        if hasattr(self, 'zipfile'):
            self.version.abs_path.mkdir()
            self.zipfile.extractall(str(self.version.abs_path))
