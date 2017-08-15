from django.conf.urls import url
from django.contrib.auth import views as auth_views

from . import forms, views


urlpatterns = [
    url(
        r'^login/$',
        auth_views.LoginView.as_view(
            authentication_form=forms.AuthenticationForm
        ),
        name='login',
    ),

    url(
        r'^register/$',
        views.RegistrationView.as_view(),
        name='register',
    ),
]
