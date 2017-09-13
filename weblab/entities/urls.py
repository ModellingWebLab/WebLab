from django.conf.urls import url

from . import views


urlpatterns = [
    url(
        r'^models/new$',
        views.ModelEntityCreateView.as_view(),
        name='new_model',
    ),

    url(
        r'^upload-file$',
        views.FileUploadView.as_view(),
        name='upload',
    ),
]
