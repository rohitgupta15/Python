from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group


ROLE_NAMES = ['Agency', 'Reception', 'ACM']


class Command(BaseCommand):
    help = 'Create default role groups.'

    def handle(self, *args, **options):
        created = 0
        for name in ROLE_NAMES:
            _, was_created = Group.objects.get_or_create(name=name)
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Roles ensured. New groups: {created}'))
