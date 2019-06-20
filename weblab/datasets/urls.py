from django.conf.urls import url

from . import views


_FILENAME = r'(?P<filename>[\w\-. \%:]+)'
_FILEVIEW = r'%s/(?P<viz>\w+)' % _FILENAME

urlpatterns = [
    url(
        '^'
        '(?P<subset>mine|public|all)?'
        '$',
        views.ExperimentalDatasetListView.as_view(),
        name='list',
    ),

    url(
        r'^new$',
        views.ExperimentalDatasetCreateView.as_view(),
        name='new',
    ),

    url(
        r'^(?P<pk>\d+)/addfiles$',
        views.ExperimentalDatasetAddFilesView.as_view(),
        name='addfiles',
    ),

    url(
        r'^(?P<pk>\d+)/upload-file$',
        views.DatasetFileUploadView.as_view(),
        name='upload_file',
    ),

    url(
        r'^(?P<pk>\d+)(?:/%s)?$' % _FILEVIEW,
        views.ExperimentalDatasetView.as_view(),
        name='detail',
    ),

    url(
        r'^(?P<pk>\d+)/files.json$',
        views.DatasetJsonView.as_view(),
        name='version_json',
    ),

    url(
        r'^(?P<pk>\d+)/download/%s$' % _FILENAME,
        views.DatasetFileDownloadView.as_view(),
        name='file_download',
    ),

    url(
        r'^(?P<pk>\d+)/archive$',
        views.DatasetArchiveView.as_view(),
        name='archive',
    ),

    # url(
    #     r'^(?P<pk>\d+)/delete$',
    #     views.ExperimentalDatasetDeleteView.as_view(),
    #     name='delete',
    # ),
    #
]
