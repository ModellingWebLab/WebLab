from django.conf.urls import url

from . import views


_COMMIT = r'(?P<sha>[^^~:/ ]+)'
_FILENAME = r'(?P<filename>[\w\-.]+)'
_FILEVIEW = r'%s/(?P<viz>\w+)' % _FILENAME
_ENTITY_TYPE = '(?P<entity_type>model|protocol)s'

urlpatterns = [
    url(
        r'^callback/check-proto$',
        views.CheckProtocolCallbackView.as_view(),
        name='protocol_check_callback',
    ),

    url(
        r'^%s/$' % _ENTITY_TYPE,
        views.EntityListView.as_view(),
        name='list',
    ),

    url(
        r'^%s/new$' % _ENTITY_TYPE,
        views.EntityCreateView.as_view(),
        name='new',
    ),

    url(
        r'^%s/(?P<pk>\d+)$' % _ENTITY_TYPE,
        views.EntityView.as_view(),
        name='detail',
    ),

    url(
        r'^%s/(?P<pk>\d+)/delete$' % _ENTITY_TYPE,
        views.EntityDeleteView.as_view(),
        name='delete',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/$' % _ENTITY_TYPE,
        views.EntityVersionListView.as_view(),
        name='version_list',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/new$' % _ENTITY_TYPE,
        views.EntityNewVersionView.as_view(),
        name='newversion',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/%s(?:/%s)?$' % (_ENTITY_TYPE, _COMMIT, _FILEVIEW),
        views.EntityVersionView.as_view(),
        name='version',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/%s/files.json$' % (_ENTITY_TYPE, _COMMIT),
        views.EntityVersionJsonView.as_view(),
        name='version_json',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/%s/compare$' % (_ENTITY_TYPE, _COMMIT),
        views.EntityCompareExperimentsView.as_view(),
        name='compare_experiments',
    ),

    url(
        r'^%s/compare(?P<versions>(/\d+:%s){1,})(?:/show/%s)?$' % (_ENTITY_TYPE, _COMMIT, _FILEVIEW),
        views.EntityComparisonView.as_view(),
        name='compare',
    ),

    url(
        r'^%s/compare(?P<versions>(/\d+:%s)*)/info$' % (_ENTITY_TYPE, _COMMIT),
        views.EntityComparisonJsonView.as_view(),
        name='compare_json',
    ),


    url(
        r'^%s/(?P<pk>\d+)/versions/%s/download/%s$' % (_ENTITY_TYPE, _COMMIT, _FILENAME),
        views.EntityFileDownloadView.as_view(),
        name='file_download',
    ),

    url(
        r'^tag/(?P<pk>\d+)/%s$' % _COMMIT,
        views.EntityTagVersionView.as_view(),
        name='tag_version',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/%s/visibility$' % (_ENTITY_TYPE, _COMMIT),
        views.ChangeVisibilityView.as_view(),
        name='change_visibility',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/%s/archive$' % (_ENTITY_TYPE, _COMMIT),
        views.EntityArchiveView.as_view(),
        name='entity_archive',
    ),

    url(
        r'^(?P<pk>\d+)/upload-file$',
        views.FileUploadView.as_view(),
        name='upload_file',
    ),

    url(
        r'^%s/(?P<pk>\d+)/collaborators$' % _ENTITY_TYPE,
        views.EntityCollaboratorsView.as_view(),
        name='entity_collaborators',
    ),

    url(
        r'^%s/diff(?P<versions>(/\d+:%s){2})/%s$' % (_ENTITY_TYPE, _COMMIT, _FILENAME),
        views.EntityDiffView.as_view(),
        name='diff',
    ),
]
