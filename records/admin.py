from django.contrib import admin

from records.models import Record, RecordHistory, RecordMonthlyTransaction, RecordWithdrawal


@admin.register(RecordHistory)
class RecordHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "record",
        "action",
        "changed_by",
        "changed_by_role",
        "timestamp",
    )
    list_filter = ("action", "changed_by_role", "timestamp")
    search_fields = ("record__record_number", "comment")
    ordering = ("-timestamp",)
    readonly_fields = ("record", "changed_by", "action", "timestamp")


class RecordMonthlyTransactionInline(admin.TabularInline):
    model = RecordMonthlyTransaction
    extra = 1
    fields = ("month", "subscription", "refund_of_withdrawals", "other_credit", "total_credit")
    readonly_fields = ("total_credit",)


class RecordWithdrawalInline(admin.TabularInline):
    model = RecordWithdrawal
    extra = 1
    fields = ("withdrawal_amount", "withdrawal_type", "withdrawal_voucher_no", "withdrawal_date", "remarks")


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = (
        "record_number",
        "subscriber_name",
        "gpf_account_number",
        "title",
        "taluka",
        "financial_year",
        "status",
        "created_by",
        "reviewed_by",
        "approved_by",
        "finalized_by",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "taluka",
        "status",
        "financial_year",
        "is_active",
        "created_at",
    )
    search_fields = (
        "record_number",
        "title",
        "description",
        "subscriber_name",
        "gpf_account_number",
        "created_by__username",
    )
    readonly_fields = (
        "record_number",
        "created_at",
        "updated_at",
        "reviewed_at",
        "approved_at",
        "forwarded_at",
        "finalized_at",
        "closing_balance",
        "amount_in_words",
    )
    fieldsets = (
        ("Record Information", {
            "fields": (
                "record_number",
                "taluka",
                "title",
                "description",
                "status",
            )
        }),
        ("GPF/Employee Details", {
            "fields": (
                "subscriber_name",
                "employee_name",
                "gpf_account_number",
                "date_of_birth",
                "ddo_name",
                "ddo_code",
                "department",
                "treasury",
            ),
            "classes": ("collapse",)
        }),
        ("Financial Information", {
            "fields": (
                "financial_year",
                "interest_rate",
                "opening_balance",
                "total_deposit",
                "total_withdrawal",
                "interest_amount",
                "closing_balance",
                "amount_in_words",
            ),
            "classes": ("collapse",)
        }),
        ("Content & Audit", {
            "fields": (
                "created_by",
                "created_at",
                "updated_by",
                "updated_at",
                "is_active",
                "deleted_at",
            )
        }),
        ("Review Workflow", {
            "fields": (
                "reviewed_by",
                "reviewed_at",
                "review_comment",
            ),
            "classes": ("collapse",)
        }),
        ("Approval Workflow", {
            "fields": (
                "approved_by",
                "approved_at",
            ),
            "classes": ("collapse",)
        }),
        ("Forwarding & Finalization", {
            "fields": (
                "forwarded_by",
                "forwarded_at",
                "finalized_by",
                "finalized_at",
            ),
            "classes": ("collapse",)
        }),
        ("Corrections", {
            "fields": (
                "correction_comment",
            ),
            "classes": ("collapse",)
        }),
    )
    inlines = [RecordMonthlyTransactionInline, RecordWithdrawalInline]
    raw_id_fields = (
        "created_by",
        "updated_by",
        "reviewed_by",
        "approved_by",
        "forwarded_by",
        "finalized_by",
    )
    ordering = ("-created_at",)
