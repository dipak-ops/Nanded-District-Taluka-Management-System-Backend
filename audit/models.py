from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = "LOGIN", "Login"
        LOGOUT = "LOGOUT", "Logout"
        USER_CREATED = "USER_CREATED", "User created"
        USER_UPDATED = "USER_UPDATED", "User updated"
        USER_DEACTIVATED = "USER_DEACTIVATED", "User deactivated"
        USER_ACTIVATED = "USER_ACTIVATED", "User activated"
        USER_DELETED = "USER_DELETED", "User deleted"
        TAHSILDAR_CREATED = "TAHSILDAR_CREATED", "Tahsildar created"
        TAHSILDAR_UPDATED = "TAHSILDAR_UPDATED", "Tahsildar updated"
        TAHSILDAR_DEACTIVATED = "TAHSILDAR_DEACTIVATED", "Tahsildar deactivated"
        RECORD_CREATED = "RECORD_CREATED", "Record created"
        RECORD_UPDATED = "RECORD_UPDATED", "Record updated"
        RECORD_DEACTIVATED = "RECORD_DEACTIVATED", "Record deactivated"
        RECORD_SUBMITTED = "RECORD_SUBMITTED", "Record submitted"
        RECORD_REVIEW_STARTED = "RECORD_REVIEW_STARTED", "Review started"
        CORRECTION_REQUESTED = "CORRECTION_REQUESTED", "Correction requested"
        RECORD_APPROVED = "RECORD_APPROVED", "Record approved"
        RECORD_FORWARDED = "RECORD_FORWARDED", "Record forwarded"
        RECORD_FINALIZED = "RECORD_FINALIZED", "Record finalized"
        PASSWORD_RESET = "PASSWORD_RESET", "Password reset"
        ROLE_CHANGED = "ROLE_CHANGED", "Role changed"
        TALUKA_CHANGED = "TALUKA_CHANGED", "Taluka changed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=40, choices=Action.choices, db_index=True)
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=50, blank=True)
    taluka = models.ForeignKey(
        "talukas.Taluka",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["taluka", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.user} at {self.timestamp}"
