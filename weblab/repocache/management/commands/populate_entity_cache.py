from django.core.management.base import BaseCommand

from entities.models import Entity

from ...populate import populate_entity_cache


class Command(BaseCommand):
    help = 'Indexes entity repositories in to cache tables'

    def add_arguments(self, parser):
        parser.add_argument('entity_id', nargs='*', type=int)

    def handle(self, *args, **options):
        entities = Entity.objects.all()
        if options.get('entity_id', []):
            entities = entities.filter(id__in=options['entity_id'])

        for entity in entities:
            populate_entity_cache(entity)
