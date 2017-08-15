from django import forms
from django.contrib.auth import forms as auth_forms


class AuthenticationForm(auth_forms.AuthenticationForm):
    username = auth_forms.UsernameField(
        max_length=255,
        widget=forms.TextInput(attrs={'autofocus': True}),
        label='Username or email',
    )
