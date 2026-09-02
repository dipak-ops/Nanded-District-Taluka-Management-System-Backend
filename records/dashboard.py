from django.db.models import Q, Count
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from accounts.models import User
from records.models import Record
from talukas.models import Taluka
from accounts.permissions import IsTahsildar, IsSuperAdmin
from records.serializers import RecordSerializer


class DashboardViewSet(viewsets.ViewSet):
    """Dashboard endpoints for different roles."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="admin")
    def admin_dashboard(self, request):
        """Get Super Admin dashboard with global statistics."""
        user = request.user
        
        if not user.is_super_admin:
            raise PermissionDenied("Only Super Admin can view this dashboard.")
        
        # Get all active records
        records = Record.objects.filter(is_active=True)
        
        # Get status counts using database aggregation
        status_summary = {}
        for status_choice in Record.Status.choices:
            status_key = status_choice[0].lower()
            status_summary[status_key] = records.filter(status=status_choice[0]).count()
        
        dashboard_data = {
            "total_talukas": Taluka.objects.filter(is_active=True).count(),
            "total_tahsildars": User.objects.filter(
                role=User.Role.TAHSILDAR,
                is_active=True
            ).count(),
            "total_users": User.objects.filter(
                role=User.Role.TALUKA_USER,
                is_active=True
            ).count(),
            "total_taluka_users": User.objects.filter(
                role=User.Role.TALUKA_USER,
                is_active=True
            ).count(),
            "active_users": User.objects.filter(is_active=True).count(),
            "inactive_users": User.objects.filter(is_active=False).count(),
            "total_records": records.count(),
            "status_summary": status_summary,
        }
        
        return Response({"success": True, "data": dashboard_data})

    @action(detail=False, methods=["get"], url_path="admin/talukas")
    def admin_talukas(self, request):
        """Get Taluka-wise summary for Super Admin."""
        user = request.user
        
        if not user.is_super_admin:
            raise PermissionDenied("Only Super Admin can view this endpoint.")
        
        records = Record.objects.filter(is_active=True)
        
        # Get Taluka-wise statistics using database queries
        taluka_stats = []
        for taluka in Taluka.objects.filter(is_active=True).prefetch_related("users"):
            taluka_records = records.filter(taluka=taluka)
            tahsildar = taluka.users.filter(role=User.Role.TAHSILDAR, is_active=True).first()
            
            taluka_stats.append({
                "id": taluka.id,
                "name": taluka.name,
                "code": taluka.code,
                "tahsildar": tahsildar.username if tahsildar else None,
                "users": taluka.users.filter(role=User.Role.TALUKA_USER, is_active=True).count(),
                "records": taluka_records.count(),
                "draft": taluka_records.filter(status=Record.Status.DRAFT).count(),
                "submitted": taluka_records.filter(status=Record.Status.SUBMITTED).count(),
                "under_review": taluka_records.filter(status=Record.Status.UNDER_REVIEW).count(),
                "correction_required": taluka_records.filter(status=Record.Status.CORRECTION_REQUIRED).count(),
                "approved": taluka_records.filter(status=Record.Status.APPROVED).count(),
                "forwarded": taluka_records.filter(status=Record.Status.FORWARDED).count(),
                "finalized": taluka_records.filter(status=Record.Status.FINALIZED).count(),
            })
        
        return Response({"success": True, "data": taluka_stats})

    @action(detail=False, methods=["get"], url_path="taluka")
    def tahsildar_dashboard(self, request):
        """Get Tahsildar dashboard with record statistics for their Taluka."""
        user = request.user
        
        if not user.is_tahsildar:
            raise PermissionDenied("Only Tahsildars can view this dashboard.")
        
        if not user.taluka_id:
            raise PermissionDenied("Tahsildar must be assigned to a Taluka.")
        
        # Get all records for this Taluka
        records = Record.objects.filter(taluka_id=user.taluka_id, is_active=True)
        
        # Get status counts
        status_counts = {}
        for status_choice in Record.Status.choices:
            status_key = status_choice[0].lower()
            status_counts[status_key] = records.filter(status=status_choice[0]).count()
        
        dashboard_data = {
            "taluka": {
                "id": user.taluka.id,
                "name": user.taluka.name,
                "code": user.taluka.code,
            },
            "tahsildar": {
                "username": user.username,
            },
            "statistics": {
                "total_users": User.objects.filter(
                    taluka_id=user.taluka_id,
                    role=User.Role.TALUKA_USER,
                    is_active=True
                ).count(),
                "active_users": User.objects.filter(
                    taluka_id=user.taluka_id,
                    is_active=True
                ).count(),
                "inactive_users": User.objects.filter(
                    taluka_id=user.taluka_id,
                    is_active=False
                ).count(),
                "total_records": records.count(),
                **{f"{k}_records": v for k, v in status_counts.items()},
            },
        }
        
        # Add pending review records
        pending_review = records.filter(status=Record.Status.SUBMITTED).values(
            "id", "record_number", "title", "created_by__username"
        )
        dashboard_data["pending_review"] = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
                "created_by": r["created_by__username"],
                "status": Record.Status.SUBMITTED,
            }
            for r in pending_review
        ]
        
        return Response({"success": True, "data": dashboard_data})

    @action(detail=False, methods=["get"], url_path="user")
    def user_dashboard(self, request):
        """Get Taluka User dashboard with their own records."""
        user = request.user
        
        if not user.is_taluka_user:
            raise PermissionDenied("Only Taluka users can view this dashboard.")
        
        if not user.taluka_id:
            raise PermissionDenied("User must be assigned to a Taluka.")
        
        # Get records created by this user only
        my_records = Record.objects.filter(
            created_by=user,
            is_active=True
        )
        
        # Get status counts
        status_counts = {}
        for status_choice in Record.Status.choices:
            status_key = status_choice[0].lower()
            status_counts[status_key] = my_records.filter(status=status_choice[0]).count()
        
        dashboard_data = {
            "user": {
                "username": user.username,
                "role": user.role,
            },
            "taluka": {
                "id": user.taluka.id,
                "name": user.taluka.name,
                "code": user.taluka.code,
            },
            "statistics": {
                "my_total_records": my_records.count(),
                **{f"{k}": v for k, v in status_counts.items()},
            },
        }
        
        # Add records needing correction
        correction_required = my_records.filter(status=Record.Status.CORRECTION_REQUIRED).values(
            "id", "record_number", "title", "correction_comment"
        )
        dashboard_data["correction_required"] = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
                "comment": r["correction_comment"],
            }
            for r in correction_required
        ]
        
        # Add draft records
        drafts = my_records.filter(status=Record.Status.DRAFT).values(
            "id", "record_number", "title", "created_at"
        )
        dashboard_data["draft_records"] = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
            }
            for r in drafts
        ]
        
        # Add recently updated records
        recently_updated = my_records.order_by("-updated_at")[:5].values(
            "id", "record_number", "title", "status", "updated_at"
        )
        dashboard_data["recently_updated"] = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
                "status": r["status"],
            }
            for r in recently_updated
        ]
        
        return Response({"success": True, "data": dashboard_data})

    @action(detail=False, methods=["get"], url_path="taluka/pending")
    def tahsildar_pending(self, request):
        """Get records pending Tahsildar review."""
        user = request.user
        
        if not user.is_tahsildar:
            raise PermissionDenied("Only Tahsildars can view this endpoint.")
        
        if not user.taluka_id:
            raise PermissionDenied("Tahsildar must be assigned to a Taluka.")
        
        records = Record.objects.filter(
            taluka_id=user.taluka_id,
            status=Record.Status.SUBMITTED,
            is_active=True
        ).values("id", "record_number", "title", "created_by__username", "created_at")
        
        data = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
                "created_by": r["created_by__username"],
                "status": Record.Status.SUBMITTED,
            }
            for r in records
        ]
        
        return Response({"success": True, "data": data})

    @action(detail=False, methods=["get"], url_path="taluka/under-review")
    def tahsildar_under_review(self, request):
        """Get records under Tahsildar review."""
        user = request.user
        
        if not user.is_tahsildar:
            raise PermissionDenied("Only Tahsildars can view this endpoint.")
        
        if not user.taluka_id:
            raise PermissionDenied("Tahsildar must be assigned to a Taluka.")
        
        records = Record.objects.filter(
            taluka_id=user.taluka_id,
            status=Record.Status.UNDER_REVIEW,
            is_active=True
        ).values("id", "record_number", "title", "created_by__username")
        
        data = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
                "created_by": r["created_by__username"],
                "status": Record.Status.UNDER_REVIEW,
            }
            for r in records
        ]
        
        return Response({"success": True, "data": data})

    @action(detail=False, methods=["get"], url_path="taluka/approved")
    def tahsildar_approved(self, request):
        """Get approved records."""
        user = request.user
        
        if not user.is_tahsildar:
            raise PermissionDenied("Only Tahsildars can view this endpoint.")
        
        if not user.taluka_id:
            raise PermissionDenied("Tahsildar must be assigned to a Taluka.")
        
        records = Record.objects.filter(
            taluka_id=user.taluka_id,
            status=Record.Status.APPROVED,
            is_active=True
        ).values("id", "record_number", "title", "created_by__username")
        
        data = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
                "created_by": r["created_by__username"],
                "status": Record.Status.APPROVED,
            }
            for r in records
        ]
        
        return Response({"success": True, "data": data})

    @action(detail=False, methods=["get"], url_path="taluka/correction-required")
    def tahsildar_correction_required(self, request):
        """Get records requiring correction."""
        user = request.user
        
        if not user.is_tahsildar:
            raise PermissionDenied("Only Tahsildars can view this endpoint.")
        
        if not user.taluka_id:
            raise PermissionDenied("Tahsildar must be assigned to a Taluka.")
        
        records = Record.objects.filter(
            taluka_id=user.taluka_id,
            status=Record.Status.CORRECTION_REQUIRED,
            is_active=True
        ).values("id", "record_number", "title", "created_by__username", "correction_comment")
        
        data = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
                "created_by": r["created_by__username"],
                "status": Record.Status.CORRECTION_REQUIRED,
                "comment": r["correction_comment"],
            }
            for r in records
        ]
        
        return Response({"success": True, "data": data})

    @action(detail=False, methods=["get"], url_path="my-records")
    def my_records(self, request):
        """Get user's own records."""
        user = request.user
        
        if not user.is_taluka_user:
            raise PermissionDenied("Only Taluka users can view this endpoint.")
        
        records = Record.objects.filter(
            created_by=user,
            is_active=True
        ).values("id", "record_number", "title", "status", "created_at", "updated_at")
        
        data = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
                "status": r["status"],
            }
            for r in records.order_by("-updated_at")
        ]
        
        return Response({"success": True, "data": data})

    @action(detail=False, methods=["get"], url_path="my-records/drafts")
    def my_drafts(self, request):
        """Get user's draft records."""
        user = request.user
        
        if not user.is_taluka_user:
            raise PermissionDenied("Only Taluka users can view this endpoint.")
        
        records = Record.objects.filter(
            created_by=user,
            status=Record.Status.DRAFT,
            is_active=True
        ).values("id", "record_number", "title", "created_at")
        
        data = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
            }
            for r in records.order_by("-created_at")
        ]
        
        return Response({"success": True, "data": data})

    @action(detail=False, methods=["get"], url_path="my-records/submitted")
    def my_submitted(self, request):
        """Get user's submitted records."""
        user = request.user
        
        if not user.is_taluka_user:
            raise PermissionDenied("Only Taluka users can view this endpoint.")
        
        records = Record.objects.filter(
            created_by=user,
            status=Record.Status.SUBMITTED,
            is_active=True
        ).values("id", "record_number", "title", "created_at")
        
        data = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
            }
            for r in records.order_by("-created_at")
        ]
        
        return Response({"success": True, "data": data})

    @action(detail=False, methods=["get"], url_path="my-records/correction-required")
    def my_correction_required(self, request):
        """Get user's records requiring correction."""
        user = request.user
        
        if not user.is_taluka_user:
            raise PermissionDenied("Only Taluka users can view this endpoint.")
        
        records = Record.objects.filter(
            created_by=user,
            status=Record.Status.CORRECTION_REQUIRED,
            is_active=True
        ).values("id", "record_number", "title", "correction_comment")
        
        data = [
            {
                "id": r["id"],
                "record_number": r["record_number"],
                "title": r["title"],
                "comment": r["correction_comment"],
            }
            for r in records
        ]
        
        return Response({"success": True, "data": data})
