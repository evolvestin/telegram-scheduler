from django.core.management.base import BaseCommand
from app.gdrive_backup import BackupManager

class Command(BaseCommand):
    help = 'Manually triggers immediate backup to Google Drive'

    def handle(self, *args, **options):
        self.stdout.write("Initializing backup process...")
        
        try:
            manager = BackupManager()
            manager.perform_backup()
            self.stdout.write(self.style.SUCCESS("Backup sequence completed successfully."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Backup failed: {e}"))