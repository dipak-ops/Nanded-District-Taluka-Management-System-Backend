from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError

from audit.services import get_client_ip, log_action
from records.models import Record, RecordHistory
from records.permissions import (
    CanAccessRecord, CanEditRecord, CanSubmitRecord, CanReviewRecord,
    CanApproveRecord, CanForwardRecord, CanFinalizeRecord
)
from records.serializers import RecordSerializer


def scoped_records(user):
    qs = Record.objects.select_related(
        "taluka", "created_by", "updated_by",
        "reviewed_by", "approved_by", "forwarded_by", "finalized_by"
    ).prefetch_related("history")
    if user.is_super_admin:
        return qs
    if user.taluka_id:
        return qs.filter(taluka_id=user.taluka_id)
    return qs.none()


def log_record_history(record, action, user, comment="", old_value="", new_value=""):
    """Log a change to record history."""
    RecordHistory.objects.create(
        record=record,
        changed_by=user,
        changed_by_role=user.role if hasattr(user, 'role') else '',
        action=action,
        old_value=old_value,
        new_value=new_value,
        comment=comment,
        taluka=record.taluka,
    )


class RecordViewSet(viewsets.ModelViewSet):
    serializer_class = RecordSerializer
    permission_classes = [IsAuthenticated, CanAccessRecord]

    def get_queryset(self):
        return scoped_records(self.request.user)

    def perform_create(self, serializer):
        record = serializer.save()
        log_action(
            user=self.request.user,
            action="RECORD_CREATED",
            target_type="Record",
            target_id=record.pk,
            taluka=record.taluka,
            ip_address=get_client_ip(self.request),
            metadata={"record_number": record.record_number},
        )
        # Log to record history
        log_record_history(
            record, 
            RecordHistory.Action.USER_UPDATED_RECORD,
            self.request.user,
            comment="Record created"
        )

    def perform_update(self, serializer):
        old_status = serializer.instance.status
        record = serializer.save()
        
        log_action(
            user=self.request.user,
            action="RECORD_UPDATED",
            target_type="Record",
            target_id=record.pk,
            taluka=record.taluka,
            ip_address=get_client_ip(self.request),
            metadata={"record_number": record.record_number},
        )
        
        # Log to record history
        log_record_history(
            record,
            RecordHistory.Action.USER_UPDATED_RECORD,
            self.request.user,
            comment="Record updated"
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.deactivate(user=request.user)
        log_action(
            user=request.user,
            action="RECORD_DEACTIVATED",
            target_type="Record",
            target_id=instance.pk,
            taluka=instance.taluka,
            ip_address=get_client_ip(request),
            metadata={"record_number": instance.record_number, "soft_delete": True},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        instance = self.get_object()
        instance.activate(user=request.user)
        log_action(
            user=request.user,
            action="RECORD_UPDATED",
            target_type="Record",
            target_id=instance.pk,
            taluka=instance.taluka,
            ip_address=get_client_ip(request),
            metadata={"activated": True},
        )
        return Response(RecordSerializer(instance, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        instance = self.get_object()
        instance.deactivate(user=request.user)
        log_action(
            user=request.user,
            action="RECORD_DEACTIVATED",
            target_type="Record",
            target_id=instance.pk,
            taluka=instance.taluka,
            ip_address=get_client_ip(request),
        )
        return Response(RecordSerializer(instance, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Submit a record for review."""
        record = self.get_object()
        
        # Check permissions
        if not CanSubmitRecord().has_object_permission(request, self, record):
            raise PermissionDenied("You cannot submit this record.")
        
        if record.status not in [Record.Status.DRAFT, Record.Status.CORRECTION_REQUIRED]:
            raise ValidationError(
                f"Cannot submit record in {record.status} status. "
                f"Only DRAFT or CORRECTION_REQUIRED records can be submitted."
            )
        
        record.status = Record.Status.SUBMITTED
        record.save(update_fields=["status", "updated_at"])
        
        log_action(
            user=request.user,
            action="RECORD_SUBMITTED",
            target_type="Record",
            target_id=record.pk,
            taluka=record.taluka,
            ip_address=get_client_ip(request),
            metadata={"record_number": record.record_number},
        )
        
        log_record_history(
            record,
            RecordHistory.Action.RECORD_SUBMITTED,
            request.user,
        )
        
        return Response(
            RecordSerializer(record, context={"request": request}).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def start_review(self, request, pk=None):
        """Start reviewing a record."""
        record = self.get_object()
        
        if not CanReviewRecord().has_object_permission(request, self, record):
            raise PermissionDenied("You cannot review this record.")
        
        if record.status != Record.Status.SUBMITTED:
            raise ValidationError(
                f"Cannot start review on record in {record.status} status."
            )
        
        record.status = Record.Status.UNDER_REVIEW
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
        
        log_action(
            user=request.user,
            action="RECORD_REVIEW_STARTED",
            target_type="Record",
            target_id=record.pk,
            taluka=record.taluka,
            ip_address=get_client_ip(request),
            metadata={"record_number": record.record_number},
        )
        
        log_record_history(
            record,
            RecordHistory.Action.RECORD_SUBMITTED,
            request.user,
        )
        
        return Response(
            RecordSerializer(record, context={"request": request}).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def request_correction(self, request, pk=None):
        """Request correction on a record."""
        record = self.get_object()
        
        if not CanReviewRecord().has_object_permission(request, self, record):
            raise PermissionDenied("You cannot request correction on this record.")
        
        if record.status != Record.Status.UNDER_REVIEW:
            raise ValidationError(
                f"Cannot request correction on record in {record.status} status."
            )
        
        comment = request.data.get("comment", "")
        
        record.status = Record.Status.CORRECTION_REQUIRED
        record.correction_comment = comment
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.save(update_fields=[
            "status", "correction_comment", "reviewed_by", "reviewed_at", "updated_at"
        ])
        
        log_action(
            user=request.user,
            action="CORRECTION_REQUESTED",
            target_type="Record",
            target_id=record.pk,
            taluka=record.taluka,
            ip_address=get_client_ip(request),
            metadata={
                "record_number": record.record_number,
                "comment": comment,
            },
        )
        
        log_record_history(
            record,
            RecordHistory.Action.RECORD_CORRECTION_REQUESTED,
            request.user,
            comment=comment,
        )
        
        return Response(
            RecordSerializer(record, context={"request": request}).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a record."""
        record = self.get_object()
        
        if not CanApproveRecord().has_object_permission(request, self, record):
            raise PermissionDenied("You cannot approve this record.")
        
        if record.status != Record.Status.UNDER_REVIEW:
            raise ValidationError(
                f"Cannot approve record in {record.status} status."
            )
        
        comment = request.data.get("comment", "")
        
        record.status = Record.Status.APPROVED
        record.approved_by = request.user
        record.approved_at = timezone.now()
        record.review_comment = comment
        record.save(update_fields=[
            "status", "approved_by", "approved_at", "review_comment", "updated_at"
        ])
        
        log_action(
            user=request.user,
            action="RECORD_APPROVED",
            target_type="Record",
            target_id=record.pk,
            taluka=record.taluka,
            ip_address=get_client_ip(request),
            metadata={
                "record_number": record.record_number,
                "comment": comment,
            },
        )
        
        log_record_history(
            record,
            RecordHistory.Action.RECORD_APPROVED,
            request.user,
            comment=comment,
        )
        
        return Response(
            RecordSerializer(record, context={"request": request}).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def forward(self, request, pk=None):
        """Forward a record to super admin."""
        record = self.get_object()
        
        if not CanForwardRecord().has_object_permission(request, self, record):
            raise PermissionDenied("You cannot forward this record.")
        
        if record.status != Record.Status.APPROVED:
            raise ValidationError(
                f"Cannot forward record in {record.status} status. "
                f"Only APPROVED records can be forwarded."
            )
        
        record.status = Record.Status.FORWARDED
        record.forwarded_by = request.user
        record.forwarded_at = timezone.now()
        record.save(update_fields=["status", "forwarded_by", "forwarded_at", "updated_at"])
        
        log_action(
            user=request.user,
            action="RECORD_FORWARDED",
            target_type="Record",
            target_id=record.pk,
            taluka=record.taluka,
            ip_address=get_client_ip(request),
            metadata={"record_number": record.record_number},
        )
        
        log_record_history(
            record,
            RecordHistory.Action.RECORD_FORWARDED,
            request.user,
        )
        
        return Response(
            RecordSerializer(record, context={"request": request}).data,
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        """Finalize a record (Super Admin only)."""
        record = self.get_object()
        
        if not CanFinalizeRecord().has_object_permission(request, self, record):
            raise PermissionDenied("Only Super Admin can finalize records.")
        
        if record.status != Record.Status.FORWARDED:
            raise ValidationError(
                f"Cannot finalize record in {record.status} status. "
                f"Only FORWARDED records can be finalized."
            )
        
        comment = request.data.get("comment", "")
        
        record.status = Record.Status.FINALIZED
        record.finalized_by = request.user
        record.finalized_at = timezone.now()
        record.save(update_fields=["status", "finalized_by", "finalized_at", "updated_at"])
        
        log_action(
            user=request.user,
            action="RECORD_FINALIZED",
            target_type="Record",
            target_id=record.pk,
            taluka=record.taluka,
            ip_address=get_client_ip(request),
            metadata={
                "record_number": record.record_number,
                "comment": comment,
            },
        )
        
        log_record_history(
            record,
            RecordHistory.Action.RECORD_FINALIZED,
            request.user,
            comment=comment,
        )
        
        return Response(
            RecordSerializer(record, context={"request": request}).data,
            status=status.HTTP_200_OK
        )
