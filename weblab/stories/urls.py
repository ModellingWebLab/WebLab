
from django.conf.urls import url

from . import views


urlpatterns = [
    url(
        r'^$',
        views.StoryListView.as_view(),
        name='stories',
    ),

    url(
        r'^new$',
        views.StoryCreateView.as_view(),
        name='story_create',
    ),

    url(
        r'^(?P<pk>\d+)/edit$',
        views.StoryEditView.as_view(),
        name='story_edit',
    ),

    url(
        r'^(?P<pk>\d+)/delete$',
        views.StoryDeleteView.as_view(),
        name='story_delete',
    ),

    url(
        r'^(?P<pk>\d+)/collaborators$',
        views.StoryCollaboratorsView.as_view(),
        name='story_collaborators',
    ),

    url(
        r'^(?P<pk>\d+)/transfer$',
        views.StoryTransferView.as_view(),
        name='story_transfer',
    ),

    url(
        r'^modelorgroup$',
        views.StoryFilterModelOrGroupView.as_view(),
        name='filter_modelorgroup',
    ),


    url(
        r'^(?P<mk>.+)/protocols$',
        views.StoryFilterProtocolView.as_view(),
        name='filter_protocol',
    ),

    url(
        r'^protocols$',
        views.StoryFilterProtocolView.as_view(),
        name='filter_protocol_no_mk',
    ),

    url(
        r'^(?P<mk>.+)/(?P<pk>\d+)/graph$',
        views.StoryFilterGraphView.as_view(),
        name='filter_graph',
    ),

    url(
        r'^(?P<mk>\w+)/graph$',
        views.StoryFilterGraphView.as_view(),
        name='filter_graph_no_pk',
    ),

    url(
        r'^graph$',
        views.StoryFilterGraphView.as_view(),
        name='filter_graph_no_keys',
    ),

    url(
        r'^(?P<mk>\w+)/(?P<pk>\d+)/experimentversions$',
        views.StoryFilterExperimentVersions.as_view(),
        name='filter_graph',
    ),

    url(
        r'^(?P<mk>.+)/(?P<pk>\d+)/experimentsnotrun$',
        views.StoryFilterExperimentsNotRunView.as_view(),
        name='filter_experiments_not_run',
    ),
    url(
        r'^(?P<mk>.+)/(?P<pk>\d+)/experimentsnotrun/(?P<gpk>\d+)/$',
        views.StoryFilterExperimentsNotRunView.as_view(),
        name='filter_experiments_not_run_existing_graph',
    ),


    url(
        r'^(?P<mk>.+)/experimentsnotrun$',
        views.StoryFilterExperimentsNotRunView.as_view(),
        name='filter_experiments_not_run_no_pk',
    ),

    url(
        r'^experimentsnotrun$',
        views.StoryFilterExperimentsNotRunView.as_view(),
        name='filter_experiments_not_run_no_keys',
    ),



    url(
        r'^(?P<mk>\w+)/experimentversions$',
        views.StoryFilterExperimentVersions.as_view(),
        name='filter_experimentversions',
    ),

    url(
        r'^experimentversions$',
        views.StoryFilterExperimentVersions.as_view(),
        name='filter_experimentversions_no_keys',
    ),


    url(
        r'^(?P<gid>\w+)/(?P<mk>\w+)/(?P<pk>\d+)/toggles$',
        views.StoryFilterGroupToggles.as_view(),
        name='filter_group_toggles',
    ),


    url(
        r'^(?P<pk>\d+)$',
        views.StoryRenderView.as_view(),
        name='story_render',
    ),

]

app_name = 'stories'
