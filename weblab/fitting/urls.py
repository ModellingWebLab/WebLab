from django.conf.urls import url

from . import views


_ENTITY_TYPE = '(?P<entity_type>fittingspec)s'

urlpatterns = [
    url(
        r'^%s/$' % _ENTITY_TYPE,
        views.FittingSpecListView.as_view(),
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
