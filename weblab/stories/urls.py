
from django.conf.urls import url

from . import views


urlpatterns = [
    url(
        r'^stories/$',
        views.StoryListView.as_view(),
        name='stories',
    ),

    url(
        r'^stories/new$',
        views.StoryCreateView.as_view(),
        name='story_create',
    ),

    url(
        r'^stories/(?P<pk>\d+)$',
        views.StoryEditView.as_view(),
        name='story_edit',
    ),

    url(
        r'^stories/(?P<pk>\d+)/delete$',
        views.StoryDeleteView.as_view(),
        name='story_delete',
    ),

    url(
        r'^stories/(?P<pk>\d+)/collaborators$',
        views.StoryCollaboratorsView.as_view(),
        name='story_collaborators',
    ),

    url(
        r'^stories/(?P<pk>\d+)/transfer$',
        views.StoryTransferView.as_view(),
        name='story_transfer',
    ),
]

app_name = 'stories'

