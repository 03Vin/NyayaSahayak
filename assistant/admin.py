from django.contrib import admin
from .models import Query


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'short_question', 'legal_area', 'confidence_label', 'top_score', 'refused', 'latency_ms', 'created_at')
    list_filter = ('refused', 'legal_area', 'confidence_label', 'include_repealed')
    search_fields = ('question', 'answer', 'user__username')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def short_question(self, obj):
        return obj.question[:60] + "..." if len(obj.question) > 60 else obj.question
    short_question.short_description = "Citizen Question"
