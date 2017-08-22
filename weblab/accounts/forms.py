from django import forms
from django.contrib.auth import forms as auth_forms

from .models import User


class AuthenticationForm(auth_forms.AuthenticationForm):
    username = auth_forms.UsernameField(
        max_length=255,
        widget=forms.TextInput(attrs={'autofocus': True}),
        label='Username or email',
    )


class RegistrationForm(auth_forms.UserCreationForm):
    class Meta(auth_forms.UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'full_name', 'institution')
        help_texts = {
            'email': 'For recovering your password, and for metadata of your files',
            'username':  'Will be displayed as the owner of your files, and must be unique',
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
