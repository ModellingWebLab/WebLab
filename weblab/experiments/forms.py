from django import forms

from .models import Runnable
from .processing import ChasteProcessingStatus


status_choices = (
    (key, key) for key in ChasteProcessingStatus.MODEL_STATUSES.keys()
)


class ExperimentSimulateCallbackForm(forms.ModelForm):
    """
    Form for simulation of experiment result callback

    This is used with the callback simulation view, by admin only.
    """
    returntype = forms.ChoiceField(label='Status', choices=status_choices)
    returnmsg = forms.CharField(widget=forms.Textarea, label='Return message', required=False)
    task_id = forms.CharField(label='Task ID', required=False)
    upload = forms.FileField(required=False)

    class Meta:
        model = Runnable
        fields = ()
