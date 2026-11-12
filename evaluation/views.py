from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from .models import EvalRun, EvalResult, EvalQuestion


@staff_member_required
def eval_results_view(request):
    runs = EvalRun.objects.all().order_by('-created_at')
    latest_run = runs.first()
    results = latest_run.results.select_related('question').all() if latest_run else []

    total_questions = EvalQuestion.objects.count()

    return render(request, 'evaluation/eval_results.html', {
        'runs': runs,
        'latest_run': latest_run,
        'results': results,
        'total_questions': total_questions,
    })
