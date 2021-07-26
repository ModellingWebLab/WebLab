from django.conf.urls import url

from . import views


_COMMIT = r'(?P<sha>[^^~:/ ]+)'
_FILENAME = r'(?P<filename>[\w\-. \%:]+)'
_FILEVIEW = r'%s/(?P<viz>\w+)' % _FILENAME
_ENTITY_TYPE = '(?P<entity_type>model|protocol)s'

urlpatterns = [
    url(
        r'^callback/check-proto$',
        views.CheckProtocolCallbackView.as_view(),
        name='protocol_check_callback',
    ),

    url(
        r'^protocols/get_interfaces$',
        views.GetProtocolInterfacesJsonView.as_view(),
        name='get_protocol_interfaces',
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
        r'^%s/(?P<pk>\d+)/versions/edit$' % _ENTITY_TYPE,
        views.EntityAlterFileView.as_view(),
        name='alter_file',
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
        r'^%s/(?P<pk>\d+)/versions/%s/fittings$' % (_ENTITY_TYPE, _COMMIT),
        views.EntityCompareFittingResultsView.as_view(),
        name='compare_fittings',
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
        r'^%s/(?P<pk>\d+)/versions/%s/runexperiments$' % (_ENTITY_TYPE, _COMMIT),
        views.EntityRunExperimentView.as_view(),
        name='runexperiments',
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
        r'^%s/(?P<pk>\d+)/transfer$' % _ENTITY_TYPE,
        views.TransferView.as_view(),
        name='transfer',
    ),

    url(
        r'^%s/(?P<pk>\d+)/rename$' % _ENTITY_TYPE,
        views.RenameView.as_view(),
        name='rename',
    ),

    url(
        r'^%s/diff(?P<versions>(/\d+:%s){2})/%s$' % (_ENTITY_TYPE, _COMMIT, _FILENAME),
        views.EntityDiffView.as_view(),
        name='diff',
    ),

    url(
        r'^modelgroups/$',
        views.ModelGroupListView.as_view(),
        name='modelgroup',
    ),


    url(
        r'^modelgroups/new/$',
        views.ModelGroupCreateView.as_view(),
        name='modelgroup_create',
    ),

    url(
        r'^modelgroups/(?P<pk>\d+)$',
        views.ModelGroupEditView.as_view(),
        name='modelgroup_edit',
    ),

    url(
        r'^modelgroups/(?P<pk>\d+)/delete$',
        views.ModelGroupDeleteView.as_view(),
        name='modelgroup_delete',
    ),

    url(
        r'^modelgroups/(?P<pk>\d+)/collaborators$',
        views.ModelGroupCollaboratorsView.as_view(),
        name='modelgroup_collaborators',
    ),

    url(
        r'^modelgroups/(?P<pk>\d+)/transfer$',
        views.ModelGroupTransferView.as_view(),
        name='modelgroup_transfer',
    ),

]

app_name = 'entities'
