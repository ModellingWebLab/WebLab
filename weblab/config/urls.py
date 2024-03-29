"""weblab URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic import TemplateView


urlpatterns = [
    url(r'^$', TemplateView.as_view(template_name='home.html'), name="home"),
    url(r'^about$', TemplateView.as_view(template_name='about.html'), name="about"),
    url(r'^contact$', TemplateView.as_view(template_name='contact.html'), name="contact"),
    url(r'^for_authors$',
        TemplateView.as_view(template_name='for_authors.html'),
        name="for_authors"),
    url(r'^privacy$', TemplateView.as_view(template_name='privacy.html'), name="privacy"),
    url(r'^accounts/', include('accounts.urls', namespace='accounts')),
    url(r'^accounts/', include('django.contrib.auth.urls')),
    url(r'^social/', include('social_django.urls', namespace='social')),
    url(r'^entities/', include('entities.urls', namespace='entities')),
    url(r'^stories/', include('stories.urls', namespace='stories')),
    url(r'^datasets/', include('datasets.urls', namespace='datasets')),
    url(r'^experiments/', include('experiments.urls', namespace='experiments')),
    url(r'^fitting/', include('fitting.urls', namespace='fitting')),
    url(r'^admin/', admin.site.urls),
]
