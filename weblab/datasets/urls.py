from django.conf.urls import url

from . import views


_FILENAME = r'(?P<filename>[\w\-. \%:]+)'
_FILEVIEW = r'%s/(?P<viz>\w+)' % _FILENAME

urlpatterns = [
    url(
        r'^/$',
        views.ExperimentalDatasetListView.as_view(),
        name='list',
    ),

    url(
        r'^new$',
        views.ExperimentalDatasetCreateView.as_view(),
        name='new',
    ),

    # url(
    #     r'^(?P<pk>\d+)$',
    #     views.ExperimentalDatasetView.as_view(),
    #     name='detail',
    # ),
    #
    # url(
    #     r'^(?P<pk>\d+)/delete$',
    #     views.ExperimentalDatasetDeleteView.as_view(),
    #     name='delete',
    # ),
    #
    # url(
    #     r'^(?P<pk>\d+)/upload-file$',
    #     views.FileUploadView.as_view(),
    #     name='upload_file',
    # ),
]
