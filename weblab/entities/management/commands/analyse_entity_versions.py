from django.core.management.base import BaseCommand

from entities.models import ModelEntity, ProtocolEntity


class Command(BaseCommand):
    help = 'Runs analysis hooks on all existing entity versions'

    def add_arguments(self, parser):
        parser.add_argument('entity_id', nargs='*', type=int)

    def handle(self, *args, **options):
        # Because we're not using properly polymorphic entities, we need to query for
        # each sub-type separately to ensure the appropriate subclass method is called.
        for manager in ModelEntity.objects, ProtocolEntity.objects:
            entities = manager.all()
            if options.get('entity_id', []):
                entities = entities.filter(id__in=options['entity_id'])

            for entity in entities:
                for commit in entity.repo.commits:
                    self.stdout.write('Analysing commit {} in {} {}'.format(
                        commit.sha[:10], entity.entity_type, entity.name))
                    entity.analyse_new_version(commit)
