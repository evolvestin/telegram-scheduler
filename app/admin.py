from django.contrib import admin
from django.utils.html import format_html
from app.models import LogEntry
from app.models import TelegramAccount, Recipient, ScheduledMessage, MessageLog

@admin.register(TelegramAccount)
class TelegramAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'is_active', 'session_status')
    
    def session_status(self, obj):
        import os
        if os.path.exists(obj.session_path):
            return "✅ Session File Exists"
        return "❌ Missing Session"

@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ('username', 'name')
    search_fields = ('username', 'name')

class MessageLogInline(admin.TabularInline):
    model = MessageLog
    readonly_fields = ('recipient', 'status', 'error_text', 'created_at')
    can_delete = False
    extra = 0

@admin.register(ScheduledMessage)
class ScheduledMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'account', 'scheduled_at', 'status', 'recipients_count')
    list_filter = ('status', 'scheduled_at')
    filter_horizontal = ('recipients',)
    inlines = [MessageLogInline]
    actions = ['force_send_now']

    def recipients_count(self, obj):
        return obj.recipients.count()

    @admin.action(description="Force Send Now (Ignore Schedule)")
    def force_send_now(self, request, queryset):
        from app.tasks import schedule_message_group
        for msg in queryset:
            schedule_message_group.delay(msg.id)
            msg.status = 'SCHEDULED'
            msg.save()
        self.message_user(request, "Selected messages queued for immediate execution.")


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'level', 'module', 'message_preview')
    list_filter = ('level', 'module', 'created_at')
    search_fields = ('message', 'module')
    readonly_fields = ('created_at', 'level', 'module', 'message', 'updated_at')

    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    
    def has_add_permission(self, request):
        return False