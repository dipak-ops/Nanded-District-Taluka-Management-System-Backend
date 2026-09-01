from django.contrib import admin

from records.models import Record, RecordHistory


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


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = (
        "record_number",
        "title",
        "taluka",
        "status",
        "created_by",
        "reviewed_by",
        "approved_by",
        "forwarded_by",
        "finalized_by",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "taluka",
        "status",
        "is_active",
        "created_at",
    )
    search_fields = (
        "record_number",
        "title",
        "description",
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
    raw_id_fields = (
        "created_by",
        "updated_by",
        "reviewed_by",
        "approved_by",
        "forwarded_by",
        "finalized_by",
    )
    ordering = ("-created_at",)
