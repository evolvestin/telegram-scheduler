import os
from django.core.management.base import BaseCommand
from telethon.sync import TelegramClient
from app.models import TelegramAccount

class Command(BaseCommand):
    help = 'Interactive login to generate session file'

    def add_arguments(self, parser):
        parser.add_argument('account_id', type=int, nargs='?', help='Target Account ID')

    def handle(self, *args, **options):
        account_id = options['account_id']

        if not account_id:
            self.stdout.write("=== Available Telegram Accounts ===")
            for acc in TelegramAccount.objects.all():
                status = "✅ Ready" if os.path.exists(acc.session_path) else "❌ Missing Session"
                self.stdout.write(f"ID: {acc.id} | Phone: {acc.phone} | Name: {acc.name} | Status: {status}")
            self.stdout.write("\nUsage: python manage.py auth_telegram <account_id>")
            return

        try:
            account = TelegramAccount.objects.get(id=account_id)
        except TelegramAccount.DoesNotExist:
            self.stderr.write(f"Error: Account ID {account_id} not found.")
            return

        self.stdout.write(f"Starting authentication for {account.phone} (ID: {account.id})...")
        
        os.makedirs(os.path.dirname(account.session_path), exist_ok=True)
        
        client = TelegramClient(account.session_path, account.api_id, account.api_hash)
        
        client.start(phone=account.phone)
        
        if os.path.exists(account.session_path):
            self.stdout.write(self.style.SUCCESS(f"Success! Session saved at: {account.session_path}"))
        else:
            self.stderr.write("Session file was not created.")
            
        client.disconnect()