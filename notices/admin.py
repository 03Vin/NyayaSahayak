from django.contrib import admin
from .models import NoticeDraft


@admin.register(NoticeDraft)
class NoticeDraftAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'notice_type', 'recipient_name', 'created_at')
    list_filter = ('notice_type', 'created_at')
    search_fields = ('user__username', 'draft_text')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def recipient_name(self, obj):
        return obj.form_data.get('recipient_name', '—')
    recipient_name.short_description = "Recipient"
