from django.db import models
from django.contrib.auth.models import User


class Query(models.Model):
    """
    Stores history of legal queries asked by citizens along with citations,
    retrieved chunks, confidence scores, and safety metrics.
    """
    AREA_CHOICES = [
        ('auto', 'Auto-Detect'),
        ('consumer', 'Consumer Protection'),
        ('tenancy', 'Tenancy / Rent Law'),
        ('labour', 'Labour / Wages'),
    ]

    CONFIDENCE_CHOICES = [
        ('High', 'High Confidence'),
        ('Medium', 'Medium Confidence'),
        ('Low', 'Low Confidence'),
        ('Refused', 'Refused / Out of Scope'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='queries')
    question = models.TextField()
    legal_area = models.CharField(max_length=50, choices=AREA_CHOICES, default='auto')
    include_repealed = models.BooleanField(default=False)
    answer = models.TextField()
    citations = models.JSONField(default=list, blank=True)
    next_steps = models.JSONField(default=list, blank=True)
    retrieved_chunk_ids = models.JSONField(default=list, blank=True)
    top_score = models.FloatField(default=0.0)
    confidence_label = models.CharField(max_length=20, choices=CONFIDENCE_CHOICES, default='Medium')
    refused = models.BooleanField(default=False, db_index=True)
    latency_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = "Refused" if self.refused else self.confidence_label
        return f"[{self.user.username}] {self.question[:40]}... ({status})"
