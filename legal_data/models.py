from django.db import models


class LegalChunk(models.Model):
    """
    Stores individual sections or sub-sections extracted from official Indian legal acts.
    """
    STATUS_CHOICES = [
        ('in_force', 'In Force'),
        ('repealed', 'Repealed'),
    ]

    AREA_CHOICES = [
        ('consumer', 'Consumer Protection'),
        ('tenancy', 'Tenancy / Rent Law'),
        ('labour', 'Labour / Wages'),
    ]

    act_name = models.CharField(max_length=255, db_index=True)
    act_year = models.PositiveIntegerField(db_index=True)
    legal_area = models.CharField(max_length=50, choices=AREA_CHOICES, db_index=True)
    legal_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_force', db_index=True)
    repealed_on = models.DateField(null=True, blank=True)
    superseded_by = models.CharField(max_length=255, null=True, blank=True)
    section_number = models.CharField(max_length=50, db_index=True)
    section_title = models.CharField(max_length=255, blank=True)
    text = models.TextField()
    chunk_id = models.CharField(max_length=100, unique=True, db_index=True)
    source_file = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['act_name', 'id']
        indexes = [
            models.Index(fields=['legal_area', 'legal_status']),
            models.Index(fields=['act_name', 'section_number']),
        ]

    def __str__(self):
        title_suffix = f" - {self.section_title}" if self.section_title else ""
        return f"{self.act_name} § {self.section_number}{title_suffix} [{self.get_legal_status_display()}]"
