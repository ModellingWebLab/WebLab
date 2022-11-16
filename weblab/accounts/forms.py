from django import forms
from django.contrib.auth import forms as auth_forms
from django.core.exceptions import ValidationError

from .models import User


class RegistrationForm(auth_forms.UserCreationForm):
    class Meta(auth_forms.UserCreationForm.Meta):
        model = User
        fields = ('full_name', 'institution', 'email')
        help_texts = {
            'email': 'For recovering your password, and for metadata of your files',
            'full_name': 'For metadata of your files',
            'institution': 'For our records',
        }


class MyAccountForm(forms.ModelForm):
    class Meta(forms.ModelForm):
        model = User
        fields = ('email', 'institution', 'receive_emails', 'receive_story_emails')
        widgets = {'receive_emails': forms.CheckboxInput(attrs={"class": 'inline'}),
                   'receive_story_emails': forms.CheckboxInput(attrs={"class": 'inline'})}

        labels = {'receive_emails': 'Inform me about finished experiments',
                  'receive_story_emails': 'Inform me when my stories are effected by new protocol/model versions'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.social_auth.exists():
            del self.fields['email']


class OwnershipTransferForm(forms.Form):
    """Used for transferring an existing entity.ownership of an existing entity or dataset """

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Email address of user'})
    )

    def _get_user(self, email):
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None

    def clean_email(self):
        email = self.cleaned_data['email']
        user = self._get_user(email)
        if not user:
            raise ValidationError('User not found')

        self.cleaned_data['user'] = user
        return email
