import logging
from django.core.management.base import BaseCommand

class LoggableBaseCommand(BaseCommand):
    def execute(self, *args, **options):
        try:
            return super().execute(*args, **options)
        except Exception as e:
            logging.error(f'Command failed: {e}', exc_info=True)
            raise e