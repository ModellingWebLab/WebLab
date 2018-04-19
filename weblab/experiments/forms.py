from django import forms

from .models import ExperimentVersion


class ExperimentSimulateCallbackForm(forms.ModelForm):
    upload = forms.FileField(required=False)

    class Meta:
        model = ExperimentVersion
        fields = ('status', 'return_text', 'task_id', 'upload')
