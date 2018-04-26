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
        r'^(?P<experiment_pk>\d+)/versions/(?P<pk>\d+)$',
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
        views.ExperimentFileListJsonView.as_view(),
        name='version-files-json',
    ),
]
