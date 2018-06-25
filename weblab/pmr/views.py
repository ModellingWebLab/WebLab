from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from .constants import CATEGORIES


CATEGORY_DICT = dict(CATEGORIES)


class BrowsePMRView(TemplateView):
    template_name = 'pmr/browse.html'


class CategoryListJsonView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({
            'categories': [
                {
                    'slug': slug,
                    'name': name,
                    'url': reverse('pmr:category', args=[slug]),
                }
                for (slug, name) in CATEGORIES
            ]
        })


class CategoryJsonView(View):
    def get(self, request, *args, **kwargs):
        slug = self.kwargs['slug']

        url = urljoin(settings.PMR['ROOT_URL'], slug)
        print(url)
        data = requests.get(
            url,
            headers={'Accept': settings.PMR['MIME_TYPE']}
        ).json()
        links = data['collection']['links']

        return JsonResponse({
            'slug': slug,
            'name': CATEGORY_DICT[slug],
            'links': [
                {
                    'url': reverse(
                        'pmr:model',
                        args=[urlparse(link['href']).path]
                    ),
                    'prompt': link['prompt'],
                }
                for link in links
            ],
        })


class ModelJsonView(View):
    def get(self, request, *args, **kwargs):
        url = urljoin(settings.PMR['ROOT_URL'], self.kwargs['uri_fragment'])
        print(url)
        data = requests.get(
            url,
            headers={'Accept': settings.PMR['MIME_TYPE']}
        ).json()

        response = {}

        item = data['collection']['items'][0]
        for link in item['links']:
            if link['rel'] == 'via' and '/rawfile' in link['href']:
                response['git_url'] = link['href'].split('/rawfile')[0]

            for entry in item['data']:
                if entry['name'] == 'title':
                    response['title'] = entry['value']

        return JsonResponse(response)
