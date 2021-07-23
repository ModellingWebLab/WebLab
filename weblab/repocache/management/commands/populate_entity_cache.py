from django.core.management.base import BaseCommand
from entities.models import Entity

from ...populate import populate_entity_cache


class Command(BaseCommand):
    help = 'Indexes entity repositories in to cache tables'

    def add_arguments(self, parser):
        parser.add_argument('entity_id', nargs='*', type=int)

    def handle(self, *args, **options):
        # Avoid 'too many open files' errors
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        print('Original limits:', soft, hard)
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
        except ValueError:
            pass  # Can easily fail while testing on Mac OS, which isn't critical!
        print('Now:', resource.getrlimit(resource.RLIMIT_NOFILE))

        entities = Entity.objects.all()
        if options.get('entity_id', []):
            entities = entities.filter(id__in=options['entity_id'])

        for entity in entities:
            if entity.repo_abs_path.exists():
                populate_entity_cache(entity)
