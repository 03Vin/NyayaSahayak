from django.contrib import admin
from .models import EvalQuestion, EvalRun, EvalResult


@admin.register(EvalQuestion)
class EvalQuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'short_question', 'legal_area', 'expected_act', 'expected_section', 'should_refuse', 'needs_verification')
    list_filter = ('legal_area', 'should_refuse', 'needs_verification', 'expects_repealed_allowed')
    search_fields = ('question', 'expected_act', 'expected_section')
    ordering = ('id',)

    def short_question(self, obj):
        return obj.question[:50] + "..." if len(obj.question) > 50 else obj.question


@admin.register(EvalRun)
class EvalRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'threshold', 'top1_accuracy', 'top3_accuracy', 'refusal_precision', 'refusal_recall', 'repealed_misuse_rate', 'avg_latency_ms', 'created_at')
    list_filter = ('threshold', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(EvalResult)
class EvalResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'run', 'question_id', 'top_score', 'correct_top1', 'correct_top3', 'refused', 'passed')
    list_filter = ('passed', 'correct_top1', 'correct_top3', 'refused')
    search_fields = ('question__question',)
    ordering = ('run', 'question')
