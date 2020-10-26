from django.conf.urls import include, url

from entities import views as entity_views

from . import views
from .models import FittingSpec


_COMMIT = r'(?P<sha>[^^~:/ ]+)'
_FILENAME = r'(?P<filename>[\w\-. \%:]+)'
_FILEVIEW = r'%s/(?P<viz>\w+)' % _FILENAME
_ENTITY_TYPE = '(?P<entity_type>%s)s' % FittingSpec.url_type


result_patterns = [
    url(
        r'^(?P<pk>\d+)/versions/$',
        views.FittingResultVersionListView.as_view(),
        name='versions',
    ),

    url(
        r'^(?P<fittingresult_pk>\d+)/versions/(?P<pk>\d+)(?:/%s)?$' % _FILEVIEW,
        views.FittingResultVersionView.as_view(),
        name='version',
    ),

    url(
        r'^(?P<fittingresult_pk>\d+)/versions/(?P<pk>\d+)/archive$',
        views.FittingResultVersionArchiveView.as_view(),
        name='archive',
    ),

    url(
        r'^(?P<fittingresult_pk>\d+)/versions/(?P<pk>\d+)/download/%s$' % _FILENAME,
        views.FittingResultFileDownloadView.as_view(),
        name='file_download',
    ),

    url(
        r'^(?P<fittingresult_pk>\d+)/versions/(?P<pk>\d+)/files.json$',
        views.FittingResultVersionJsonView.as_view(),
        name='version_json',
    ),

    url(
        r'^(?P<pk>\d+)/delete$',
        views.FittingResultDeleteView.as_view(),
        name='delete',
    ),

    url(
        r'^(?P<fittingresult_pk>\d+)/versions/(?P<pk>\d+)/delete$',
        views.FittingResultVersionDeleteView.as_view(),
        name='delete_version',
    ),

    url(
        r'^compare(?P<version_pks>(/\d+){1,})(?:/show/%s)?$' % _FILEVIEW,
        views.FittingResultComparisonView.as_view(),
        name='compare',
    ),

    url(
        r'^compare(?P<version_pks>(/\d+)*)/info$',
        views.FittingResultComparisonJsonView.as_view(),
        name='compare_json',
    ),

    url(
        r'^new$',
        views.FittingResultCreateView.as_view(),
        name='new'
    ),

    url(
        r'^new/filter$',
        views.FittingResultFilterJsonView.as_view(),
        name='filter_json',
    ),

    url(
        r'^rerun$',
        views.FittingResultRerunView.as_view(),
        name='rerun'
    ),
]

urlpatterns = [
    url(
        r'^%s/$' % _ENTITY_TYPE,
        entity_views.EntityListView.as_view(),
        name='list',
    ),

    url(
        r'^%s/new$' % _ENTITY_TYPE,
        views.FittingSpecCreateView.as_view(),
        name='new',
    ),

    url(
        r'^%s/(?P<pk>\d+)$' % _ENTITY_TYPE,
        entity_views.EntityView.as_view(),
        name='detail',
    ),

    url(
        r'^%s/(?P<pk>\d+)/delete$' % _ENTITY_TYPE,
        entity_views.EntityDeleteView.as_view(),
        name='delete',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/$' % _ENTITY_TYPE,
        entity_views.EntityVersionListView.as_view(),
        name='version_list',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/new$' % _ENTITY_TYPE,
        views.FittingSpecNewVersionView.as_view(),
        name='newversion',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/edit$' % _ENTITY_TYPE,
        entity_views.EntityAlterFileView.as_view(),
        name='alter_file',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/%s(?:/%s)?$' % (_ENTITY_TYPE, _COMMIT, _FILEVIEW),
        entity_views.EntityVersionView.as_view(),
        name='version',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/%s/files.json$' % (_ENTITY_TYPE, _COMMIT),
        entity_views.EntityVersionJsonView.as_view(),
        name='version_json',
    ),

    url(
        r'^%s/compare(?P<versions>(/\d+:%s){1,})(?:/show/%s)?$' % (_ENTITY_TYPE, _COMMIT, _FILEVIEW),
        entity_views.EntityComparisonView.as_view(),
        name='compare',
    ),

    url(
        r'^%s/compare(?P<versions>(/\d+:%s)*)/info$' % (_ENTITY_TYPE, _COMMIT),
        entity_views.EntityComparisonJsonView.as_view(),
        name='compare_json',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/%s/fittings$' % (_ENTITY_TYPE, _COMMIT),
        entity_views.EntityCompareFittingResultsView.as_view(),
        name='compare_fittings',
    ),

    url(
        r'^%s/compare(?P<versions>(/\d+:%s){1,})(?:/show/%s)?$' % (_ENTITY_TYPE, _COMMIT, _FILEVIEW),
        entity_views.EntityComparisonView.as_view(),
        name='compare',
    ),

    url(
        r'^%s/compare(?P<versions>(/\d+:%s)*)/info$' % (_ENTITY_TYPE, _COMMIT),
        entity_views.EntityComparisonJsonView.as_view(),
        name='compare_json',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/%s/download/%s$' % (_ENTITY_TYPE, _COMMIT, _FILENAME),
        entity_views.EntityFileDownloadView.as_view(),
        name='file_download',
    ),

    url(
        r'^tag/(?P<pk>\d+)/%s$' % _COMMIT,
        entity_views.EntityTagVersionView.as_view(),
        name='tag_version',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/%s/visibility$' % (_ENTITY_TYPE, _COMMIT),
        entity_views.ChangeVisibilityView.as_view(),
        name='change_visibility',
    ),

    url(
        r'^%s/(?P<pk>\d+)/versions/%s/archive$' % (_ENTITY_TYPE, _COMMIT),
        entity_views.EntityArchiveView.as_view(),
        name='entity_archive',
    ),

    url(
        r'^(?P<pk>\d+)/upload-file$',
        entity_views.FileUploadView.as_view(),
        name='upload_file',
    ),

    url(
        r'^%s/(?P<pk>\d+)/collaborators$' % _ENTITY_TYPE,
        entity_views.EntityCollaboratorsView.as_view(),
        name='entity_collaborators',
    ),

    url(
        r'^%s/diff(?P<versions>(/\d+:%s){2})/%s$' % (_ENTITY_TYPE, _COMMIT, _FILENAME),
        entity_views.EntityDiffView.as_view(),
        name='diff',
    ),

    url(
        r'^%s/(?P<pk>\d+)/transfer$' % _ENTITY_TYPE,
        entity_views.TransferView.as_view(),
        name='transfer',
    ),

    url(
        r'^%s/(?P<pk>\d+)/rename$' % _ENTITY_TYPE,
        views.FittingSpecRenameView.as_view(),
        name='rename',
    ),

    url(
        r'^%s/(?P<pk>\d+)/results'
        '/?'
        r'(?P<subset>mine|public|all)?'
        r'$' % _ENTITY_TYPE,
        views.FittingSpecResultsMatrixView.as_view(),
        name='matrix',
    ),

    url(
        r'^%s/(?P<pk>\d+)/results/matrix$' % _ENTITY_TYPE,
        views.FittingSpecResultsMatrixJsonView.as_view(),
        name='matrix_json',
    ),

    url(
        r'^results/', include(result_patterns, namespace='result')
    ),
]
