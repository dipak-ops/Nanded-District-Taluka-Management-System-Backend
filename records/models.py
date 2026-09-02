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
    
    # GPF/Employee Details
    subscriber_name = models.CharField(max_length=255, blank=True)
    employee_name = models.CharField(max_length=255, blank=True)
    gpf_account_number = models.CharField(max_length=50, blank=True, db_index=True)
    date_of_birth = models.DateField(null=True, blank=True)
    ddo_name = models.CharField(max_length=255, blank=True)
    ddo_code = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=255, blank=True)
    treasury = models.CharField(max_length=255, blank=True)
    
    # Financial Details
    financial_year = models.CharField(max_length=9, blank=True, db_index=True)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Balance Summary
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_deposit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_withdrawal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    interest_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    amount_in_words = models.CharField(max_length=512, blank=True)
    
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


class RecordMonthlyTransaction(models.Model):
    class Month(models.TextChoices):
        APRIL = "04", "April"
        MAY = "05", "May"
        JUNE = "06", "June"
        JULY = "07", "July"
        AUGUST = "08", "August"
        SEPTEMBER = "09", "September"
        OCTOBER = "10", "October"
        NOVEMBER = "11", "November"
        DECEMBER = "12", "December"
        JANUARY = "01", "January"
        FEBRUARY = "02", "February"
        MARCH = "03", "March"

    record = models.ForeignKey(
        Record,
        on_delete=models.CASCADE,
        related_name="monthly_transactions",
    )
    month = models.CharField(max_length=7, blank=True, help_text="MM/YYYY format")
    subscription = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    refund_of_withdrawals = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    other_credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("record", "month")
        ordering = ["record", "month"]
        indexes = [
            models.Index(fields=["record", "month"]),
        ]

    def save(self, *args, **kwargs):
        self.total_credit = self.subscription + self.refund_of_withdrawals + self.other_credit
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.record.record_number} - {self.month}"


class RecordWithdrawal(models.Model):
    record = models.ForeignKey(
        Record,
        on_delete=models.CASCADE,
        related_name="withdrawals",
    )
    withdrawal_amount = models.DecimalField(max_digits=15, decimal_places=2)
    withdrawal_type = models.CharField(max_length=100, blank=True)
    withdrawal_voucher_no = models.CharField(max_length=50, blank=True)
    withdrawal_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-withdrawal_date", "-created_at"]

    def __str__(self):
        return f"{self.record.record_number} - Withdrawal {self.withdrawal_voucher_no}"
