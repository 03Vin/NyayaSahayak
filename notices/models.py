from django.db import models
from django.contrib.auth.models import User


class NoticeDraft(models.Model):
    """
    Stores draft legal notices generated for users based on structured facts.
    """
    NOTICE_TYPES = [
        ('security_deposit', 'Security Deposit Refund Demand (Tenancy)'),
        ('defective_product', 'Defective Product / Deficient Service Demand (Consumer)'),
        ('unpaid_wages', 'Unpaid Wages Demand (Labour)'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notice_drafts')
    notice_type = models.CharField(max_length=50, choices=NOTICE_TYPES)
    form_data = models.JSONField(default=dict)
    draft_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notice_type_display()} - {self.user.username} ({self.created_at.strftime('%Y-%m-%d')})"
