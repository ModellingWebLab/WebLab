from django.conf.urls import url
from django.contrib.auth import views as auth_views

from . import forms


urlpatterns = [
    url(
        r'^login/$',
        auth_views.LoginView.as_view(
            authentication_form=forms.AuthenticationForm
        ),
        name='login'
    ),

    url(
        r'^logout/$',
        auth_views.LogoutView.as_view(),
        name='logout'
    ),
]
