from django.apps import apps
from django.test import TestCase

from stories.apps import StoriesConfig


class ReportsConfigTest(TestCase):
    def test_apps(self):
        self.assertEqual(StoriesConfig.name, 'stories')
        self.assertEqual(apps.get_app_config('stories').name, 'stories')
