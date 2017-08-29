from django import forms
from django.contrib.auth import forms as auth_forms

from .models import User


class RegistrationForm(auth_forms.UserCreationForm):
    class Meta(auth_forms.UserCreationForm.Meta):
        model = User
        fields = ('email', 'full_name', 'institution')
        help_texts = {
            'email': 'For recovering your password, and for metadata of your files',
            'full_name': 'For metadata of your files',
            'institution': 'For our records',
        }


class MyAccountForm(forms.ModelForm):
    class Meta(forms.ModelForm):
        model = User
        fields = ('institution', 'receive_emails')
        labels = {
            'receive_emails': 'Inform me about finished experiments',
        }
