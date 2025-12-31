from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from app.models import ScheduledMessage
from app.tasks import schedule_message_group

@receiver(post_save, sender=ScheduledMessage)
def on_message_save(sender, instance, created, **kwargs):
    """
    If a message is saved with status PENDING and has a future time, schedule it.
    """
    if instance.status == 'PENDING' and instance.scheduled_at:
        now = timezone.now()
        if instance.scheduled_at > now:
            # We need recipients to be set before scheduling, handled via m2m_changed usually,
            # but for simplicity, we assume recipients are added.
            # However, post_save fires before M2M. 
            # Real scheduling logic is better invoked explicitly or via periodic check for robustness.
            pass

@receiver(m2m_changed, sender=ScheduledMessage.recipients.through)
def on_recipients_changed(sender, instance, action, **kwargs):
    if action == 'post_add' and instance.status == 'PENDING':
        _schedule_if_needed(instance)

def _schedule_if_needed(instance):
    now = timezone.now()
    if instance.scheduled_at > now:
        # Schedule the task
        task = schedule_message_group.apply_async(
            args=[instance.id], 
            eta=instance.scheduled_at
        )
        instance.celery_task_id = task.id
        instance.status = 'SCHEDULED'
        instance.save(update_fields=['status', 'celery_task_id'])