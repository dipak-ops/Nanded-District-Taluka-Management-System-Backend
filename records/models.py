from django.conf import settings
from django.db import models
from django.utils import timezone


class Record(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
        CORRECTION_REQUIRED = "CORRECTION_REQUIRED", "Correction Required"
        APPROVED = "APPROVED", "Approved"
        FORWARDED = "FORWARDED", "Forwarded"
        FINALIZED = "FINALIZED", "Finalized"

    taluka = models.ForeignKey(
        "talukas.Taluka",
        on_delete=models.PROTECT,
        related_name="records",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_records",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_records",
        null=True,
        blank=True,
    )
    record_number = models.CharField(max_length=32, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Workflow fields
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_records",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_records",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    forwarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="forwarded_records",
        null=True,
        blank=True,
    )
    forwarded_at = models.DateTimeField(null=True, blank=True)
    
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="finalized_records",
        null=True,
        blank=True,
    )
    finalized_at = models.DateTimeField(null=True, blank=True)
    
    correction_comment = models.TextField(blank=True)
    
    class Meta:
        ordering = ["taluka__code", "record_number"]
        indexes = [
            models.Index(fields=["taluka", "is_active"]),
            models.Index(fields=["taluka", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.record_number} - {self.title}"

    def deactivate(self, user=None):
        self.is_active = False
        self.status = self.Status.DRAFT
        self.deleted_at = timezone.now()
        if user:
            self.updated_by = user
        self.save()

    def activate(self, user=None):
        self.is_active = True
        self.status = self.Status.DRAFT
        self.deleted_at = None
        if user:
            self.updated_by = user
        self.save()


def next_record_number(taluka):
    prefix = taluka.code
    last = (
        Record.objects.filter(record_number__startswith=f"{prefix}-")
        .order_by("-record_number")
        .values_list("record_number", flat=True)
        .first()
    )
    if last:
        try:
            seq = int(last.split("-")[-1]) + 1
        except ValueError:
            seq = Record.objects.filter(taluka=taluka).count() + 1
    else:
        seq = 1
    while Record.objects.filter(record_number=f"{prefix}-{seq:03d}").exists():
        seq += 1
    return f"{prefix}-{seq:03d}"


class RecordHistory(models.Model):
    class Action(models.TextChoices):
        USER_UPDATED_RECORD = "USER_UPDATED_RECORD", "User updated record"
        TAHSILDAR_UPDATED_RECORD = "TAHSILDAR_UPDATED_RECORD", "Tahsildar updated record"
        RECORD_SUBMITTED = "RECORD_SUBMITTED", "Record submitted"
        RECORD_CORRECTION_REQUESTED = "RECORD_CORRECTION_REQUESTED", "Correction requested"
        RECORD_APPROVED = "RECORD_APPROVED", "Record approved"
        RECORD_FORWARDED = "RECORD_FORWARDED", "Record forwarded"
        RECORD_FINALIZED = "RECORD_FINALIZED", "Record finalized"

    record = models.ForeignKey(
        Record,
        on_delete=models.CASCADE,
        related_name="history",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    changed_by_role = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=50, choices=Action.choices)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    comment = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    taluka = models.ForeignKey(
        "talukas.Taluka",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["record", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.record.record_number} - {self.action} at {self.timestamp}"
