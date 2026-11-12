from django.db import models
from django.utils import timezone


class EvalQuestion(models.Model):
    """
    Test questions used to benchmark retrieval accuracy, refusal rate,
    and repealed-law misuse detection.
    """
    AREA_CHOICES = [
        ('consumer', 'Consumer Protection'),
        ('tenancy', 'Tenancy / Rent Law'),
        ('labour', 'Labour / Wages'),
        ('unrelated', 'Unrelated / Out-of-Scope'),
    ]

    question = models.TextField()
    expected_act = models.CharField(max_length=255, blank=True)
    expected_section = models.CharField(max_length=100, blank=True)
    should_refuse = models.BooleanField(default=False)
    legal_area = models.CharField(max_length=50, choices=AREA_CHOICES, blank=True)
    expects_repealed_allowed = models.BooleanField(default=False)
    needs_verification = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['id']

    def __str__(self):
        refusal_str = " [Expect Refusal]" if self.should_refuse else ""
        return f"Q{self.id}: {self.question[:60]}...{refusal_str}"


class EvalRun(models.Model):
    """
    Summary metrics of an automated evaluation test run.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    threshold = models.FloatField()
    top1_accuracy = models.FloatField(default=0.0)
    top3_accuracy = models.FloatField(default=0.0)
    refusal_precision = models.FloatField(default=0.0)
    refusal_recall = models.FloatField(default=0.0)
    repealed_misuse_rate = models.FloatField(default=0.0)
    avg_latency_ms = models.FloatField(default=0.0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Run {self.id} @ {self.created_at.strftime('%Y-%m-%d %H:%M')} (Threshold={self.threshold:.2f}, Top1={self.top1_accuracy*100:.1f}%)"


class EvalResult(models.Model):
    """
    Per-question detailed result for an evaluation run.
    """
    run = models.ForeignKey(EvalRun, on_delete=models.CASCADE, related_name='results')
    question = models.ForeignKey(EvalQuestion, on_delete=models.CASCADE, related_name='results')
    retrieved = models.JSONField(default=list)
    top_score = models.FloatField(default=0.0)
    correct_top1 = models.BooleanField(default=False)
    correct_top3 = models.BooleanField(default=False)
    refused = models.BooleanField(default=False)
    passed = models.BooleanField(default=False)

    class Meta:
        ordering = ['run', 'question']

    def __str__(self):
        res = "PASS" if self.passed else "FAIL"
        return f"Run {self.run_id} - Q{self.question_id}: {res}"
