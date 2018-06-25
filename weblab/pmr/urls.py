from django.conf.urls import url

from . import views


urlpatterns = [
    url(
        r'^$',
        views.BrowsePMRView.as_view(),
        name='browse'
    ),

    url(
        r'^categories/$',
        views.CategoryListJsonView.as_view(),
        name='categories'
    ),

    url(
        r'^categories/(?P<slug>[-\w]+)/$',
        views.CategoryJsonView.as_view(),
        name='category'
    ),

    url(
        r'^models(?P<uri_fragment>.+)$',
        views.ModelJsonView.as_view(),
        name='model'
    ),
]
