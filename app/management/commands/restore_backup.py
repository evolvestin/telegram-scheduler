from django.core.management.base import BaseCommand
from app.gdrive_backup import BackupManager
import sys

class Command(BaseCommand):
    help = 'Restores Database and Sessions from Google Drive (DESTRUCTIVE)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Do not prompt for confirmation',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("WARNING: This will OVERWRITE the current database and sessions."))
        
        if not options['no_input']:
            confirm = input("Are you sure you want to proceed? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR("Restoration cancelled."))
                return

        self.stdout.write("Initializing restoration process...")
        
        try:
            manager = BackupManager()
            manager.perform_restore()
            self.stdout.write(self.style.SUCCESS("Restoration completed successfully."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Restoration failed: {e}"))
            sys.exit(1)