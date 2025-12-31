import os
from django.db import models
from django.conf import settings
from django.utils import timezone

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class TelegramAccount(BaseModel):
    name = models.CharField(max_length=100, help_text="Friendly name for the account")
    api_id = models.IntegerField(help_text="Get from my.telegram.org")
    api_hash = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    session_file = models.CharField(max_length=255, editable=False)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.session_file:
            # Generate a consistent session filename based on phone
            clean_phone = ''.join(filter(str.isdigit, self.phone))
            self.session_file = f"session_{clean_phone}"
        super().save(*args, **kwargs)

    @property
    def session_path(self):
        return os.path.join(settings.DATA_DIR, f"{self.session_file}.session")

    def __str__(self):
        return f"{self.name} ({self.phone})"

class Recipient(BaseModel):
    name = models.CharField(max_length=100, blank=True)
    username = models.CharField(max_length=100, unique=True, help_text="Username (with @) or Phone number")
    
    def __str__(self):
        return self.name or self.username

class ScheduledMessage(BaseModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SCHEDULED', 'Scheduled in Queue'),
        ('PARTIAL', 'Partially Sent'),
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]

    account = models.ForeignKey(TelegramAccount, on_delete=models.CASCADE)
    recipients = models.ManyToManyField(Recipient, related_name='messages')
    text = models.TextField()
    media_path = models.CharField(max_length=255, blank=True, null=True, help_text="Path to file in /data/")
    scheduled_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    retry_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Msg to {self.recipients.count()} users at {self.scheduled_at}"

class MessageLog(BaseModel):
    message = models.ForeignKey(ScheduledMessage, on_delete=models.CASCADE, related_name='logs')
    recipient = models.ForeignKey(Recipient, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20)
    error_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Log: {self.status} for {self.recipient}"
    

class LogEntry(BaseModel):
    level = models.CharField(max_length=10)
    module = models.CharField(max_length=100)
    message = models.TextField()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Log entry'
        verbose_name_plural = 'Log entries'

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M:%S')}] [{self.level}] {self.module}"