
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
        r'^(?P<pk>\d+)$',
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
        r'^(?P<mk>\w+)/protocols$',
        views.StoryFilterProtocolView.as_view(),
        name='filter_protocol',
    ),

]

app_name = 'stories'

