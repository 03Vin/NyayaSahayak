import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.contrib import messages

from .models import NoticeDraft
from .forms import NoticeGuidedForm
from .services.generator import generate_notice_draft, NOTICE_TEMPLATES_CONFIG
from .services.pdf import generate_notice_pdf

logger = logging.getLogger(__name__)


@login_required
def notice_list_view(request):
    """
    Displays available notice types to draft and previously generated notices.
    """
    drafts = NoticeDraft.objects.filter(user=request.user)
    return render(request, 'notices/notice_list.html', {
        'drafts': drafts,
        'configs': NOTICE_TEMPLATES_CONFIG
    })


@login_required
def notice_create_view(request, notice_type):
    """
    Guided step-by-step form to collect facts and draft a legal demand notice.
    """
    if notice_type not in NOTICE_TEMPLATES_CONFIG:
        messages.error(request, "Invalid notice type selected.")
        return redirect('notice_list')

    config = NOTICE_TEMPLATES_CONFIG[notice_type]

    if request.method == 'POST':
        form = NoticeGuidedForm(request.POST)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            # Convert date objects to ISO strings for JSON storage
            data_dict = {}
            for k, v in cleaned_data.items():
                data_dict[k] = v.isoformat() if hasattr(v, 'isoformat') else v

            # Generate draft via LLM
            draft_text = generate_notice_draft(notice_type, data_dict)

            # Save draft in database
            draft_obj = NoticeDraft.objects.create(
                user=request.user,
                notice_type=notice_type,
                form_data=data_dict,
                draft_text=draft_text
            )

            messages.success(request, f"{config['title']} generated successfully. You may preview and edit it below.")
            return redirect('notice_detail', draft_id=draft_obj.id)
    else:
        form = NoticeGuidedForm()

    return render(request, 'notices/notice_form.html', {
        'form': form,
        'notice_type': notice_type,
        'config': config
    })


@login_required
def notice_detail_view(request, draft_id):
    """
    Previews the notice draft text, allows in-place editing, and provides PDF download button.
    """
    draft_obj = get_object_or_404(NoticeDraft, id=draft_id, user=request.user)
    config = NOTICE_TEMPLATES_CONFIG.get(draft_obj.notice_type, {})

    if request.method == 'POST':
        updated_text = request.POST.get('draft_text', '').strip()
        if updated_text:
            draft_obj.draft_text = updated_text
            draft_obj.save()
            messages.success(request, "Notice draft updated successfully.")
            return redirect('notice_detail', draft_id=draft_obj.id)

    return render(request, 'notices/notice_detail.html', {
        'draft_obj': draft_obj,
        'config': config
    })


@login_required
def notice_export_pdf_view(request, draft_id):
    """
    Streams the compiled PDF directly to the user's browser.
    """
    draft_obj = get_object_or_404(NoticeDraft, id=draft_id, user=request.user)
    config = NOTICE_TEMPLATES_CONFIG.get(draft_obj.notice_type, {})
    title = config.get('title', 'LEGAL DEMAND NOTICE')

    pdf_buffer = generate_notice_pdf(draft_obj.draft_text, title)

    filename = f"legal_notice_{draft_obj.notice_type}_{draft_obj.id}.pdf"
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
