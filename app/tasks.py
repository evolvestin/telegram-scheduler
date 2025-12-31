import logging
import asyncio
from celery import shared_task
from django.utils import timezone
from telethon import errors

from app.gdrive_backup import BackupManager
from app.models import ScheduledMessage, MessageLog
from app.telegram_utils import TelethonWrapper

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=5)
def schedule_message_group(self, message_id):
    try:
        msg_obj = ScheduledMessage.objects.get(id=message_id)
    except ScheduledMessage.DoesNotExist:
        logger.error(f"Message {message_id} not found.")
        return

    # Mark as processing
    if msg_obj.status != 'PARTIAL':
        msg_obj.status = 'PARTIAL'
        msg_obj.save(update_fields=['status'])

    account = msg_obj.account
    recipients = msg_obj.recipients.all()
    
    # We run the async logic in a sync wrapper
    try:
        run_async_sending_logic(self, msg_obj, account, recipients)
        
        # If we reach here, update status to SENT
        msg_obj.status = 'SENT'
        msg_obj.save(update_fields=['status'])
        
    except errors.FloodWaitError as e:
        # Critical Telegram Limit - retry task after wait time
        logger.warning(f"FloodWait hit. Retrying in {e.seconds} seconds.")
        raise self.retry(exc=e, countdown=e.seconds + 5)
    except Exception as e:
        logger.error(f"Task failed: {e}")
        msg_obj.status = 'FAILED'
        msg_obj.save(update_fields=['status'])
        # Retry with exponential backoff for other errors
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

def run_async_sending_logic(task_instance, msg_obj, account, recipients):
    """
    Helper function to run the async loop inside the synchronous Celery worker.
    Creates a new event loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def _process():
        wrapper = TelethonWrapper(account.session_path, account.api_id, account.api_hash)
        async with wrapper:
            for recipient in recipients:
                # Check if already sent successfully to avoid duplicates on retry
                if MessageLog.objects.filter(message=msg_obj, recipient=recipient, status='SENT').exists():
                    continue

                target = recipient.username # User ID or Username
                try:
                    await wrapper.send_message(target, msg_obj.text, file=msg_obj.media_path)
                    
                    MessageLog.objects.create(
                        message=msg_obj,
                        recipient=recipient,
                        status='SENT'
                    )
                except errors.FloodWaitError:
                    raise # Bubbles up to Celery retry
                except Exception as e:
                    MessageLog.objects.create(
                        message=msg_obj,
                        recipient=recipient,
                        status='FAILED',
                        error_text=str(e)
                    )
                    # We continue to next recipient, but log the error
    
    try:
        loop.run_until_complete(_process())
    finally:
        loop.close()


@shared_task
def perform_backup_task():
    logger.info("Starting scheduled backup...")
    BackupManager().perform_backup()
    logger.info("Backup finished.")