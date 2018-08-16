from django.conf.urls import url

from . import views


_COMMIT = r'(?P<sha>[^^~:/ ]+)'
_FILENAME = r'(?P<filename>[\w\-.]+)'
_FILEVIEW = r'%s/(?P<viz>\w+)' % _FILENAME

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
        views.EntityView.as_view(),
        {'entity_type': 'model'},
        name='model',
    ),

    url(
        r'^models/(?P<pk>\d+)/delete$',
        views.EntityDeleteView.as_view(),
        {'entity_type': 'model'},
        name='model_delete',
    ),

    url(
        r'^models/(?P<pk>\d+)/versions/$',
        views.ModelEntityVersionListView.as_view(),
        name='model_versions',
    ),

    url(
        r'^models/(?P<pk>\d+)/versions/new$',
        views.ModelEntityNewVersionView.as_view(),
        name='model_newversion',
    ),

    url(
        r'^models/(?P<pk>\d+)/versions/%s(?:/%s)?$' % (_COMMIT, _FILEVIEW),
        views.ModelEntityVersionView.as_view(),
        name='model_version',
    ),

    url(
        r'^models/(?P<pk>\d+)/versions/%s/files.json$' % _COMMIT,
        views.ModelEntityVersionJsonView.as_view(),
        name='model_version_json',
    ),

    url(
        r'^models/(?P<pk>\d+)/versions/%s/compare$' % _COMMIT,
        views.ModelEntityVersionCompareView.as_view(),
        name='model_version_compare',
    ),

    url(
        r'^models/(?P<pk>\d+)/versions/%s/download/%s$' % (_COMMIT, _FILENAME),
        views.ModelEntityFileDownloadView.as_view(),
        name='model_file_download',
    ),

    url(
        r'^tag/(?P<pk>\d+)/%s$' % _COMMIT,
        views.EntityTagVersionView.as_view(),
        name='tag_version',
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
        views.EntityView.as_view(),
        {'entity_type': 'protocol'},
        name='protocol',
    ),

    url(
        r'^protocols/(?P<pk>\d+)/delete$',
        views.EntityDeleteView.as_view(),
        {'entity_type': 'protocol'},
        name='protocol_delete',
    ),

    url(
        r'^protocols/(?P<pk>\d+)/versions/$',
        views.ProtocolEntityVersionListView.as_view(),
        name='protocol_versions',
    ),

    url(
        r'^protocols/(?P<pk>\d+)/versions/new$',
        views.ProtocolEntityNewVersionView.as_view(),
        name='protocol_newversion',
    ),

    url(
        r'^protocols/(?P<pk>\d+)/versions/%s(?:/%s)?$' % (_COMMIT, _FILEVIEW),
        views.ProtocolEntityVersionView.as_view(),
        name='protocol_version',
    ),

    url(
        r'^protocols/(?P<pk>\d+)/versions/%s/files.json$' % _COMMIT,
        views.ProtocolEntityVersionJsonView.as_view(),
        name='protocol_version_json',
    ),

    url(
        r'^protocols/(?P<pk>\d+)/versions/%s/compare$' % _COMMIT,
        views.ProtocolEntityVersionCompareView.as_view(),
        name='protocol_version_compare',
    ),

    url(
        r'^protocols/(?P<pk>\d+)/versions/%s/download/%s$' % (_COMMIT, _FILENAME),
        views.ProtocolEntityFileDownloadView.as_view(),
        name='protocol_file_download',
    ),

    url(
        r'^(?P<entity_type>model|protocol)s/(?P<pk>\d+)/versions/%s/archive$' % _COMMIT,
        views.EntityArchiveView.as_view(),
        name='entity_archive',
    ),

    url(
        r'^(?P<pk>\d+)/upload-file$',
        views.FileUploadView.as_view(),
        name='upload_file',
    ),
]
