from django.conf.urls import url

from . import views


urlpatterns = [
    url(
        r'^models/$',
        views.ModelEntityListView.as_view(),
        name='models',
    ),

    url(
        r'^models/new$',
        views.ModelEntityCreateView.as_view(),
        name='new_model',
    ),

    url(
        r'^models/(?P<pk>\d+)$',
        views.ModelEntityView.as_view(),
        name='model',
    ),

    url(
        r'^models/(?P<pk>\d+)/versions/new$',
        views.ModelEntityNewVersionView.as_view(),
        name='model_newversion',
    ),

    url(
        r'^models/(?P<pk>\d+)/versions/(?P<sha>\w+)$',
        views.ModelEntityVersionView.as_view(),
        name='model_version',
    ),

    url(
        r'^protocols/$',
        views.ProtocolEntityListView.as_view(),
        name='protocols',
    ),

    url(
        r'^protocols/new$',
        views.ProtocolEntityCreateView.as_view(),
        name='new_protocol',
    ),

    url(
        r'^protocols/(?P<pk>\d+)$',
        views.ProtocolEntityView.as_view(),
        name='protocol',
    ),

    url(
        r'^protocols/(?P<pk>\d+)/versions/new$',
        views.ProtocolEntityNewVersionView.as_view(),
        name='protocol_newversion',
    ),

    url(
        r'^protocols/(?P<pk>\d+)/versions/(?P<sha>\w+)$',
        views.ProtocolEntityVersionView.as_view(),
        name='protocol_version',
    ),

    url(
        r'^(?P<pk>\d+)/upload-file$',
        views.FileUploadView.as_view(),
        name='upload_file',
    ),
]
