import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

from .models import Query
from .services.rag import answer_legal_query
from .services.rate_limiter import is_rate_limited, get_remaining_requests

logger = logging.getLogger(__name__)


@login_required
def ask_view(request):
    """
    Main Ask page for citizens to submit legal queries.
    Handles rate limiting, character validation, retrieval, guardrail, and response rendering.
    """
    context = {
        'default_area': request.GET.get('area', 'auto'),
        'remaining_quota': get_remaining_requests(request.user.id),
        'max_chars': settings.MAX_QUESTION_LENGTH,
    }

    if request.method == 'POST':
        # Check hourly rate limit
        if is_rate_limited(request.user.id):
            messages.error(
                request,
                f"Hourly question limit reached ({settings.ASK_RATE_LIMIT_PER_HOUR} requests/hour). "
                "Please wait before submitting another query."
            )
            return render(request, 'assistant/ask.html', context)

        question = request.POST.get('question', '').strip()
        legal_area = request.POST.get('legal_area', 'auto')
        include_repealed = bool(request.POST.get('include_repealed'))

        if len(question) < 5:
            messages.error(request, "Please enter a detailed legal dispute question (at least 5 characters).")
            return render(request, 'assistant/ask.html', context)

        if len(question) > settings.MAX_QUESTION_LENGTH:
            question = question[:settings.MAX_QUESTION_LENGTH]

        context['submitted_question'] = question
        context['default_area'] = legal_area
        context['include_repealed'] = include_repealed

        # Run RAG Pipeline
        result = answer_legal_query(
            question=question,
            legal_area=legal_area,
            include_repealed=include_repealed,
            user=request.user
        )

        # Save Query Record in database
        query_record = Query.objects.create(
            user=request.user,
            question=question,
            legal_area=legal_area,
            include_repealed=include_repealed,
            answer=result["answer"],
            citations=result["citations"],
            next_steps=result["next_steps"],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
            top_score=result["top_score"],
            confidence_label=result["confidence_label"],
            refused=result["refused"],
            latency_ms=result["latency_ms"]
        )

        context['result'] = result
        context['query_id'] = query_record.id
        context['remaining_quota'] = get_remaining_requests(request.user.id)

    return render(request, 'assistant/ask.html', context)


@login_required
def history_view(request):
    """
    Displays past queries asked by the logged-in user.
    """
    user_queries = Query.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'assistant/history.html', {
        'queries': user_queries
    })


@login_required
def query_detail_view(request, query_id):
    """
    Detailed view for a specific past query, showing full statutory analysis and retrieved sections.
    """
    query_obj = get_object_or_404(Query, id=query_id, user=request.user)

    # Fetch corresponding chunk objects for full source text
    from legal_data.models import LegalChunk
    retrieved_chunks = LegalChunk.objects.filter(chunk_id__in=query_obj.retrieved_chunk_ids)

    return render(request, 'assistant/query_detail.html', {
        'query_obj': query_obj,
        'retrieved_chunks': retrieved_chunks
    })
