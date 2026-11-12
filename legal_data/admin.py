from django.contrib import admin
from .models import LegalChunk


@admin.register(LegalChunk)
class LegalChunkAdmin(admin.ModelAdmin):
    list_display = ('act_name', 'section_number', 'section_title', 'legal_area', 'legal_status', 'created_at')
    list_filter = ('legal_area', 'legal_status', 'act_name')
    search_fields = ('act_name', 'section_number', 'section_title', 'text')
    readonly_fields = ('chunk_id', 'created_at')
    ordering = ('act_name', 'id')
