import logging
import os
from django.contrib.auth import get_user_model
from app.gdrive_backup import BackupManager
from app.management.base import LoggableBaseCommand

class Command(LoggableBaseCommand):
    help = "Creates a superuser if it doesn't exist, using environment variables."

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')

        if not user_model.objects.filter(username=username).exists():
            logging.info(f"Superuser '{username}' not found, creating...")
            email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
            password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
            if password:
                user_model.objects.create_superuser(username=username, email=email, password=password)
                logging.info(f"Superuser '{username}' created.")
            else:
                logging.warning('DJANGO_SUPERUSER_PASSWORD not set, skipping superuser creation.')
        else:
            logging.info(f"Superuser '{username}' already exists.")