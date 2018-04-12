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
]
