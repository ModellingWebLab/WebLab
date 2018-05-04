from django.conf.urls import url

from . import views


urlpatterns = [
    url(
        r'^$',
        views.ExperimentsView.as_view(),
        name='list',
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
        r'^(?P<experiment_pk>\d+)/versions/(?P<pk>\d+)(?:/(?P<filename>[\w.]+)/(?P<viz>\w+))?$',
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
        r'^(?P<experiment_pk>\d+)/versions/(?P<pk>\d+)/download/(?P<filename>[\w\-.]+)$',
        views.ExperimentFileDownloadView.as_view(),
        name='file_download',
    ),

    url(
        r'^(?P<experiment_pk>\d+)/versions/(?P<pk>\d+)/archive$',
        views.ExperimentArchiveView.as_view(),
        name='archive',
    ),
]
