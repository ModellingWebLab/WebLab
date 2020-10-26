from django.conf.urls import url

from . import views


_COMMIT = r'(?P<sha>[^^~:/ ]+)'
_FILENAME = r'(?P<filename>[\w\-. \%:]+)'
_FILEVIEW = r'%s/(?P<viz>\w+)' % _FILENAME

urlpatterns = [
    url(
        '^'
        '(?P<subset>mine|public|all)?'
        '/?'
        r'(?:models(?P<model_pks>(/\d+)+)'
        '(?:/versions(?P<model_versions>(/%s)+))?)?'
        '/?'
        r'(?:protocols(?P<protocol_pks>(/\d+)+)'
        '(?:/versions(?P<protocol_versions>(/%s)+))?)?'
        '$' % (_COMMIT, _COMMIT.replace('sha', 'sha1')),
        views.ExperimentsView.as_view(),
        name='list',
    ),

    url(
        r'^tasks$',
        views.ExperimentTasks.as_view(),
        name='tasks',
    ),

    url(
        r'^new$',
        views.NewExperimentView.as_view(),
        name='new',
    ),

    url(
        r'^callback$',
        views.ExperimentCallbackView.as_view(),
        name='callback',
    ),

    url(
        r'^matrix$',
        views.ExperimentMatrixJsonView.as_view(),
        name='matrix',
    ),

    url(
        r'^(?P<pk>\d+)/versions/$',
        views.ExperimentVersionListView.as_view(),
        name='versions',
    ),

    url(
        r'^(?P<pk>\d+)/delete$',
        views.ExperimentDeleteView.as_view(),
        name='delete',
    ),

    url(
        r'^(?P<experiment_pk>\d+)/versions/(?P<pk>\d+)/delete$',
        views.ExperimentVersionDeleteView.as_view(),
        name='delete_version',
    ),

    url(
        r'^(?P<experiment_pk>\d+)/versions/(?P<pk>\d+)(?:/%s)?$' % _FILEVIEW,
        views.ExperimentVersionView.as_view(),
        name='version',
    ),

    url(
        r'^(?P<experiment_pk>\d+)/versions/(?P<pk>\d+)/callback$',
        views.ExperimentSimulateCallbackView.as_view(),
        name='simulate_callback',
    ),

    url(
        r'^(?P<experiment_pk>\d+)/versions/(?P<pk>\d+)/files.json$',
        views.ExperimentVersionJsonView.as_view(),
        name='version_json',
    ),

    url(
        r'^(?P<experiment_pk>\d+)/versions/(?P<pk>\d+)/download/%s$' % _FILENAME,
        views.ExperimentFileDownloadView.as_view(),
        name='file_download',
    ),

    url(
        r'^(?P<experiment_pk>\d+)/versions/(?P<pk>\d+)/archive$',
        views.ExperimentVersionArchiveView.as_view(),
        name='archive',
    ),

    url(
        r'^compare(?P<version_pks>(/\d+){1,})(?:/show/%s)?$' % _FILEVIEW,
        views.ExperimentComparisonView.as_view(),
        name='compare',
    ),

    url(
        r'^compare(?P<version_pks>(/\d+)*)/info$',
        views.ExperimentComparisonJsonView.as_view(),
        name='compare_json',
    ),
]

app_name = 'experiments'