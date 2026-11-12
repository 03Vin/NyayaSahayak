// NyayaSahayak - Client-side UI Helpers (< 60 lines vanilla JS)
document.addEventListener('DOMContentLoaded', function () {
    // 1. Live Character Counter for Question Textarea
    const questionInput = document.getElementById('question-input');
    const charCounter = document.getElementById('char-counter');
    if (questionInput && charCounter) {
        const updateCounter = () => {
            const count = questionInput.value.length;
            charCounter.textContent = `${count} / 1000 characters`;
            charCounter.className = count > 950 ? 'text-danger small' : 'text-muted small';
        };
        questionInput.addEventListener('input', updateCounter);
        updateCounter();
    }

    // 2. Submit Button Loading Spinner & Form Submission Guard
    const askForm = document.getElementById('ask-form');
    const submitBtn = document.getElementById('ask-submit-btn');
    const spinner = document.getElementById('ask-spinner');
    const btnText = document.getElementById('ask-btn-text');

    if (askForm && submitBtn) {
        askForm.addEventListener('submit', function (e) {
            if (questionInput && questionInput.value.trim().length === 0) {
                e.preventDefault();
                return;
            }
            submitBtn.disabled = true;
            if (spinner) spinner.classList.remove('d-none');
            if (btnText) btnText.textContent = 'Searching Laws & Analyzing...';
        });
    }

    // 3. Citation Expansion Toggle Helper (for dynamic badges)
    document.querySelectorAll('.citation-toggle-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const targetId = this.getAttribute('data-bs-target');
            const target = document.querySelector(targetId);
            if (target) {
                const isExpanded = target.classList.contains('show');
                this.setAttribute('aria-expanded', !isExpanded);
            }
        });
    });
});

