from django.conf.urls import url
from django.contrib.auth import views as auth_views

from . import views


urlpatterns = [
    url(
        r'^login/$',
        auth_views.LoginView.as_view(),
        name='login',
    ),

    url(
        r'^register/$',
        views.RegistrationView.as_view(),
        name='register',
    ),

    url(
        r'^myaccount/$',
        views.MyAccountView.as_view(),
        name='myaccount',
    ),

    url(
        r'^(?P<pk>\d+)/delete/$',
        views.UserDeleteView.as_view(),
        name='delete',
    ),

]
app_name = 'accounts'
