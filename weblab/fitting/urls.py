from django.conf.urls import url

from entities import views as entity_views

from . import views
from .models import FittingSpec


_ENTITY_TYPE = '(?P<entity_type>%s)s' % FittingSpec.url_type

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

    # url(
    #     r'^specs/(?P<pk>\d+)$',
    #     views.FittingSpecView.as_view(),
    #     name='detail',
    # ),

    # url(
    #     r'^specs/(?P<pk>\d+)/delete$',
    #     views.FittingSpecDeleteView.as_view(),
    #     name='delete',
    # ),
]
