from django.shortcuts import render
from .models import LegalChunk
from django.conf import settings
import json
from pathlib import Path


def laws_covered_view(request):
    """
    Renders details of all legal acts covered in NyayaSahayak,
    including legal status, commencement dates, and indexed section counts.
    """
    status_file = settings.ACTS_DIR / "act_status.json"
    status_data = {}
    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status_data = json.load(f)
        except Exception:
            status_data = {}

    # Query chunk counts grouped by act
    chunks = LegalChunk.objects.all()
    act_counts = {}
    for chunk in chunks:
        act_counts[chunk.act_name] = act_counts.get(chunk.act_name, 0) + 1

    return render(request, 'legal_data/laws_covered.html', {
        'status_data': status_data,
        'act_counts': act_counts,
        'total_chunks': chunks.count(),
        'wages_commencement': settings.WAGES_CODE_COMMENCEMENT,
    })
